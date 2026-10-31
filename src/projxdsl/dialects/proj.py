from __future__ import annotations

from collections.abc import Sequence
from enum import auto
from typing import ClassVar

from xdsl.dialects.builtin import (
    ArrayAttr,
    FlatSymbolRefAttrConstr,
    FunctionType,
    StringAttr,
    SymbolNameConstraint,
    SymbolRefAttr,
    i1,
)
from xdsl.dialects.utils import (
    EnumAttribute,
    parse_func_op_like,
    print_func_op_like,
)
from xdsl.ir import (
    Attribute,
    Block,
    Dialect,
    Operation,
    OpTrait,
    ParametrizedAttribute,
    Region,
    SSAValue,
    TypeAttribute,
    VerifyException,
)
from xdsl.irdl import (
    IRDLOperation,
    irdl_attr_definition,
    irdl_op_definition,
    irdl_to_attr_constraint,
    operand_def,
    opt_region_def,
    prop_def,
    region_def,
    result_def,
    traits_def,
    var_operand_def,
    var_result_def,
)
from xdsl.parser import AttrParser, Parser
from xdsl.printer import Printer
from xdsl.traits import (
    HasParent,
    IsolatedFromAbove,
    IsTerminator,
    NoTerminator,
    SymbolOpInterface,
    SymbolTable,
    SymbolUserOpInterface,
)
from xdsl.utils.str_enum import StrEnum

from projxdsl.dialects.angle import AngleType
from projxdsl.func_kind import FuncKind


class Basis(StrEnum):
    """
    Basis enum for qubit borrow annotations.
    """

    X = auto()
    Y = auto()
    Z = auto()


class State(StrEnum):
    """
    State enum for ket states.
    """

    ZERO = auto()
    ONE = auto()
    PLUS = auto()
    MINUS = auto()
    LEFT = auto()
    RIGHT = auto()

    def get_basis(self) -> Basis:
        """Get the measurement basis for this state."""
        match self:
            case State.ZERO | State.ONE:
                return Basis.Z
            case State.PLUS | State.MINUS:
                return Basis.X
            case State.LEFT | State.RIGHT:
                return Basis.Y


@irdl_attr_definition
class StateAttr(EnumAttribute[State]):
    """
    State attribute for ket states (|0>, |1>, |+>, |->, |L>, |R>).
    """

    name = "proj.state"

    @classmethod
    def ZERO(cls) -> StateAttr:
        return StateAttr(State.ZERO)

    @classmethod
    def ONE(cls) -> StateAttr:
        return StateAttr(State.ONE)

    @classmethod
    def PLUS(cls) -> StateAttr:
        return StateAttr(State.PLUS)

    @classmethod
    def MINUS(cls) -> StateAttr:
        return StateAttr(State.MINUS)

    @classmethod
    def LEFT(cls) -> StateAttr:
        return StateAttr(State.LEFT)

    @classmethod
    def RIGHT(cls) -> StateAttr:
        return StateAttr(State.RIGHT)

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> State:
        with parser.in_angle_brackets():
            return super().parse_parameter(parser)

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            super().print_parameter(printer)


@irdl_attr_definition
class ProjectionType(ParametrizedAttribute, TypeAttribute):
    """
    Projection type (proj).
    """

    name = "proj.projection"


@irdl_attr_definition
class QubitType(ParametrizedAttribute, TypeAttribute):
    """
    qubit - Qubit type.
    """

    name = "proj.qubit"


class FuncOpBase(IRDLOperation):
    """
    Base class for function operations.
    All function kinds share the same structure.
    """

    FUNC_KIND: ClassVar[FuncKind]

    body = region_def("single_block")
    sym_name = prop_def(SymbolNameConstraint())
    function_type = prop_def(FunctionType)

    traits = traits_def(IsolatedFromAbove(), SymbolOpInterface())

    @classmethod
    def parse(cls, parser: Parser) -> FuncOpBase:
        (
            name,
            input_types,
            return_types,
            region,
            extra_attrs,
            _,
            _,
        ) = parse_func_op_like(
            parser,
            reserved_attr_names=("sym_name", "function_type"),
        )
        func = cls(
            sym_name=name,
            function_type=FunctionType.from_lists(input_types, return_types),
            body=region,
        )
        if extra_attrs is not None:
            func.attributes.update(extra_attrs.data)
        return func

    def print(self, printer: Printer) -> None:
        print_func_op_like(
            printer,
            self.sym_name,
            self.function_type,
            self.body,
            self.attributes,
            reserved_attr_names=(
                "sym_name",
                "function_type",
            ),
        )

    def verify_(self) -> None:
        entry_block = self.body.blocks.first
        assert entry_block is not None
        block_arg_types = entry_block.arg_types
        if self.function_type.inputs.data != tuple(block_arg_types):
            raise VerifyException(
                "Expected entry block argument types to match function input types"
            )

    def __init__(
        self,
        sym_name: str | StringAttr,
        function_type: FunctionType,
        body: Region | None = None,
    ):
        if isinstance(sym_name, str):
            sym_name = StringAttr(sym_name)
        if body is None:
            body = Region()

        super().__init__(
            properties={
                "function_type": function_type,
                "sym_name": sym_name,
            },
            regions=[body],
        )


class AllowedInFuncKinds(OpTrait):
    """
    Trait that verifies an operation only appears in specific function kinds.

    Uses the function kind hierarchy: PURE ⊆ UNITARY ⊆ MIXED
    Operations specify a minimum required kind, and can only appear in
    functions of that kind or higher.
    """

    def __init__(self, min_kind: FuncKind):
        """
        Initialize the trait with a minimum required function kind.

        Args:
            min_kind: Minimum FuncKind required for this operation
                     (e.g., FuncKind.MIXED for alloc/measure)
        """
        self.min_kind = min_kind

    def verify(self, op: Operation) -> None:
        """Verify that the operation appears only in allowed function kinds."""

        # Find the ancestor function operation
        func_op = op.parent_op()
        while func_op is not None and not isinstance(func_op, FuncOpBase):
            func_op = func_op.parent_op()

        if func_op is None:
            # No function ancestor, allow the operation
            return

        if func_op.FUNC_KIND < self.min_kind:
            raise VerifyException(
                f"Operation '{op.name}' is not allowed in"
                f" {func_op.FUNC_KIND.display_name} contexts."
                f" Context must be at least {self.min_kind.display_name}."
            )


ProjectionConstr = irdl_to_attr_constraint(ProjectionType)


@irdl_op_definition
class NotOp(IRDLOperation):
    """
    Negation operation for projections.
    Takes a projection (proj) and returns a projection.
    """

    name = "proj.not"

    input = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$input attr-dict"

    def __init__(self, input: SSAValue):
        super().__init__(operands=[input], result_types=[ProjectionType()])


@irdl_op_definition
class AndOp(IRDLOperation):
    """
    Conjunction operation for projections.
    Takes two projections and returns a projection.
    """

    name = "proj.and"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class OrOp(IRDLOperation):
    """
    Disjunction operation for projections.
    Takes two projections and returns a projection.
    """

    name = "proj.or"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class XorOp(IRDLOperation):
    """
    Exclusive-or operation for projections.
    Takes two projections and returns a projection.
    """

    name = "proj.xor"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class FromBoolOp(IRDLOperation):
    """
    Cast operation from boolean to projection.
    Takes a boolean (i1) and returns a projection.
    """

    name = "proj.from_bool"

    input = operand_def(i1)
    result = result_def(ProjectionType)

    assembly_format = "$input attr-dict"

    def __init__(self, input: SSAValue):
        super().__init__(operands=[input], result_types=[ProjectionType()])


@irdl_op_definition
class AllocOp(IRDLOperation):
    """
    Qubit allocation operation.
    Allocates a qubit in the specified state.
    Only allowed in mixed functions.
    """

    name = "proj.alloc"

    state = prop_def(StateAttr)
    result = result_def(QubitType)

    traits = traits_def(AllowedInFuncKinds(FuncKind.MIXED))

    assembly_format = "`` $state attr-dict `:` type($result)"

    def __init__(self, state: StateAttr):
        super().__init__(
            properties={"state": state},
            result_types=[QubitType()],
        )


@irdl_op_definition
class EqOp(IRDLOperation):
    """
    Projection creation operation.
    Creates a projection by comparing a qubit to a ket state.
    The state determines the basis (ZERO/ONE=Z, PLUS/MINUS=X, LEFT/RIGHT=Y).
    """

    name = "proj.eq"

    qubit = operand_def(QubitType)
    state = prop_def(StateAttr)
    result = result_def(ProjectionType)

    assembly_format = "$qubit `:` type($qubit) `,` qualified($state) attr-dict"

    def __init__(self, qubit: SSAValue, state: StateAttr):
        super().__init__(
            operands=[qubit],
            properties={"state": state},
            result_types=[ProjectionType()],
        )


@irdl_op_definition
class PhaseOp(IRDLOperation):
    """
    Phase operation.
    Takes an angle operand.
    Only allowed in unitary and mixed functions.
    """

    name = "proj.phase"

    angle = operand_def(AngleType)

    traits = traits_def(AllowedInFuncKinds(FuncKind.UNITARY))

    assembly_format = "$angle attr-dict"

    def __init__(self, angle: SSAValue):
        super().__init__(operands=[angle])


@irdl_op_definition
class MeasureOp(IRDLOperation):
    """
    Measurement operation.
    Takes a projection and returns a boolean (i1).
    Only allowed in mixed functions.
    """

    name = "proj.measure"

    projection = operand_def(ProjectionType)
    result = result_def(i1)

    traits = traits_def(AllowedInFuncKinds(FuncKind.MIXED))

    assembly_format = "$projection attr-dict"

    def __init__(self, projection: SSAValue):
        super().__init__(operands=[projection], result_types=[i1])


@irdl_op_definition
class IfOp(IRDLOperation):
    """
    Conditional operation for projections.
    Executes the true region if the condition projection is true.
    Only allowed in unitary and mixed functions.
    """

    name = "proj.if"

    condition = operand_def(ProjectionType)
    true_region = region_def("single_block")
    false_region = opt_region_def("single_block")

    traits = traits_def(
        NoTerminator(),
        AllowedInFuncKinds(FuncKind.UNITARY),
    )

    def __init__(
        self,
        condition: SSAValue,
        true_region: Region | Sequence[Block] | Sequence[Operation],
        false_region: Region | Sequence[Block] | Sequence[Operation] | None = None,
    ):
        super().__init__(
            operands=[condition],
            regions=[true_region, false_region],
        )

    @classmethod
    def parse(cls, parser: Parser) -> IfOp:
        condition = parser.parse_operand(ProjectionType())
        true_region = parser.parse_region()
        # Ensure true_region has at least one block
        # (required by single_block constraint)
        if not true_region.blocks:
            true_region.add_block(Block())
        if parser.parse_optional_keyword("else"):
            false_region = parser.parse_region()
            # Ensure false_region has at least one block
            # (required by single_block constraint)
            if not false_region.blocks:
                false_region.add_block(Block())
        else:
            false_region = None
        parser.parse_optional_attr_dict()
        return cls(condition, true_region, false_region)

    def print(self, printer: Printer) -> None:
        printer.print_string(" ")
        printer.print_operand(self.condition)
        printer.print_string(" ")
        printer.print_region(
            self.true_region,
            print_entry_block_args=False,
            print_block_terminators=True,
        )
        if self.false_region is not None and bool(self.false_region.blocks):
            printer.print_string(" else ")
            printer.print_region(
                self.false_region,
                print_entry_block_args=False,
                print_block_terminators=True,
            )
        if bool(self.attributes.keys()):
            printer.print_attr_dict(self.attributes)


@irdl_op_definition
class PureOp(FuncOpBase):
    """
    Pure classical function operation.
    Classical computation only - no quantum operations allowed.
    """

    name = "proj.pure"

    FUNC_KIND: ClassVar = FuncKind.PURE


@irdl_op_definition
class UnitaryOp(FuncOpBase):
    """
    Unitary function operation.
    Quantum operations without measurement or allocation.
    """

    name = "proj.unitary"

    FUNC_KIND: ClassVar = FuncKind.UNITARY


@irdl_op_definition
class MixedOp(FuncOpBase):
    """
    Mixed quantum channel function operation.
    Full quantum operations including measurement and allocation.
    """

    name = "proj.mixed"

    FUNC_KIND: ClassVar = FuncKind.MIXED


@irdl_op_definition
class ReturnOp(IRDLOperation):
    """
    Return operation for function operations.
    Terminates a proj.pure, proj.unitary, or proj.mixed function.
    """

    name = "proj.return"

    arguments = var_operand_def()

    assembly_format = "attr-dict ($arguments^ `:` type($arguments))?"

    traits = traits_def(HasParent(FuncOpBase), IsTerminator())

    def verify_(self) -> None:
        func_op = self.parent_op()
        assert isinstance(func_op, FuncOpBase)

        function_return_types = func_op.function_type.outputs.data
        return_types = self.arguments.types
        if function_return_types != return_types:
            raise VerifyException(
                "Expected arguments to have the same types as the function output "
                f"types: expected {func_op.function_type.outputs}, "
                f"got {ArrayAttr(return_types)}"
            )

    def __init__(self, *operands: SSAValue):
        super().__init__(operands=[operands])


class CallOpSymbolUserOpInterface(SymbolUserOpInterface):
    """Interface for verifying proj.call operations."""

    def verify(self, op: Operation) -> None:
        from projxdsl.dialects.proj import FuncOpBase

        assert isinstance(op, CallOp)

        found_callee = SymbolTable.lookup_symbol(op, op.callee)
        if not found_callee:
            raise VerifyException(f"'{op.callee}' could not be found in symbol table")

        if not isinstance(found_callee, FuncOpBase):
            raise VerifyException(f"'{op.callee}' does not reference a valid function")

        # Check function kind compatibility
        # Hierarchy: pure ⊆ unitary ⊆ mixed
        caller_func = op.parent_op()
        while caller_func is not None and caller_func.name not in (
            "proj.pure",
            "proj.unitary",
            "proj.mixed",
        ):
            caller_func = caller_func.parent_op()

        if caller_func is not None:
            callee_kind = found_callee.name
            caller_kind = caller_func.name

            # pure can only call pure
            # unitary can call pure, unitary
            # mixed can call pure, unitary, mixed
            kind_hierarchy = {"proj.pure": 0, "proj.unitary": 1, "proj.mixed": 2}
            callee_level = kind_hierarchy.get(callee_kind, -1)
            caller_level = kind_hierarchy.get(caller_kind, -1)

            if callee_level > caller_level:
                raise VerifyException(
                    f"Cannot call {callee_kind} function from {caller_kind} function. "
                    f"{caller_kind} functions can only call functions of equal or "
                    "lower privilege level."
                )

        if len(found_callee.function_type.inputs) != len(op.arguments):
            raise VerifyException(
                f"incorrect number of operands for callee: "
                f"expected {len(found_callee.function_type.inputs)}, "
                f"got {len(op.arguments)}"
            )

        if len(found_callee.function_type.outputs) != len(op.result_types):
            raise VerifyException(
                f"incorrect number of results for callee: "
                f"expected {len(found_callee.function_type.outputs)}, "
                f"got {len(op.result_types)}"
            )

        for idx, (found_operand, operand) in enumerate(
            zip(found_callee.function_type.inputs, (arg.type for arg in op.arguments))
        ):
            if found_operand != operand:
                raise VerifyException(
                    f"operand type mismatch: expected operand type {found_operand}, "
                    f"but provided {operand} for operand number {idx}"
                )

        for idx, (found_res, res) in enumerate(
            zip(found_callee.function_type.outputs, op.result_types)
        ):
            if found_res != res:
                raise VerifyException(
                    f"result type mismatch: expected result type {found_res}, "
                    f"but provided {res} for result number {idx}"
                )


@irdl_op_definition
class CallOp(IRDLOperation):
    """
    Function call operation.
    Calls a function by symbol reference with the given arguments.
    """

    name = "proj.call"

    callee = prop_def(FlatSymbolRefAttrConstr)
    arguments = var_operand_def()
    res = var_result_def()

    traits = traits_def(
        CallOpSymbolUserOpInterface(),
    )

    assembly_format = (
        "$callee `(` $arguments `)` attr-dict `:` functional-type($arguments, $res)"
    )

    def __init__(
        self,
        callee: str | SymbolRefAttr,
        arguments: Sequence[SSAValue],
        result_types: Sequence[Attribute],
    ):
        if isinstance(callee, str):
            callee = SymbolRefAttr(callee)
        super().__init__(
            operands=[arguments],
            result_types=[result_types],
            properties={"callee": callee},
        )


Proj = Dialect(
    "proj",
    [
        AllocOp,
        NotOp,
        AndOp,
        OrOp,
        XorOp,
        FromBoolOp,
        EqOp,
        MeasureOp,
        PhaseOp,
        IfOp,
        ReturnOp,
        CallOp,
        PureOp,
        UnitaryOp,
        MixedOp,
    ],
    [
        StateAttr,
        QubitType,
        ProjectionType,
    ],
)
