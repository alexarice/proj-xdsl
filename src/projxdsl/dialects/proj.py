from __future__ import annotations

from collections.abc import Sequence
from enum import auto

from xdsl.dialects.builtin import (
    ArrayAttr,
    FunctionType,
    NoneAttr,
    StringAttr,
    SymbolNameConstraint,
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
    prop_def,
    region_def,
    result_def,
    traits_def,
    var_operand_def,
)
from xdsl.parser import AttrParser, Parser
from xdsl.printer import Printer
from xdsl.traits import (
    HasParent,
    IsolatedFromAbove,
    IsTerminator,
    SingleBlockImplicitTerminator,
)
from xdsl.utils.str_enum import StrEnum

from projxdsl.dialects.angle import AngleType
from projxdsl.traits import AllowedInFuncKinds


class Basis(StrEnum):
    """
    Basis enum for qubit borrow annotations.
    """

    X = auto()
    Y = auto()
    Z = auto()


@irdl_attr_definition
class BasisAttr(EnumAttribute[Basis]):
    """
    Basis attribute (basis ∈ {X, Y, Z}).
    """

    name = "proj.basis"

    @classmethod
    def X(cls) -> BasisAttr:
        return BasisAttr(Basis.X)

    @classmethod
    def Y(cls) -> BasisAttr:
        return BasisAttr(Basis.Y)

    @classmethod
    def Z(cls) -> BasisAttr:
        return BasisAttr(Basis.Z)

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> Basis:
        with parser.in_angle_brackets():
            return super().parse_parameter(parser)

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            super().print_parameter(printer)


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
    qubit - Qubit type with optional basis borrow annotation.
    """

    name = "proj.qubit"

    borrow_type: BasisAttr | NoneAttr

    def print_parameters(self, printer: Printer) -> None:
        if isinstance(self.borrow_type, BasisAttr):
            self.borrow_type.print_parameter(printer)

    @classmethod
    def parse_parameters(cls, parser: AttrParser) -> tuple[BasisAttr | NoneAttr]:
        if parser.parse_optional_characters("<") is None:
            return (NoneAttr(),)
        basis = parser.parse_str_enum(Basis)
        parser.parse_characters(">", " to close proj.qubit parameters")
        return (BasisAttr(basis),)

    def __init__(self, borrow_type: BasisAttr | NoneAttr = NoneAttr()):
        super().__init__(borrow_type)


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

    traits = traits_def(AllowedInFuncKinds(("proj.mixed",)))

    assembly_format = "`` $state attr-dict `:` type($result)"

    def __init__(self, state: StateAttr):
        super().__init__(
            properties={"state": state},
            result_types=[QubitType(NoneAttr())],
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

    traits = traits_def(AllowedInFuncKinds(("proj.unitary", "proj.mixed")))

    assembly_format = "$angle attr-dict"

    def __init__(self, angle: SSAValue):
        super().__init__(operands=[angle])


@irdl_op_definition
class YieldOp(IRDLOperation):
    """
    Yield operation for proj control flow.
    Terminates a proj.if region.
    """

    name = "proj.yield"

    arguments = var_operand_def()

    assembly_format = "attr-dict ($arguments^ `:` type($arguments))?"

    traits = traits_def(IsTerminator())

    def __init__(self, *operands: SSAValue):
        super().__init__(operands=[operands])


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

    traits = traits_def(AllowedInFuncKinds(("proj.mixed",)))

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
    false_region = region_def()

    traits = traits_def(
        SingleBlockImplicitTerminator(YieldOp),
        AllowedInFuncKinds(("proj.unitary", "proj.mixed")),
    )

    def __init__(
        self,
        condition: SSAValue,
        true_region: Region | Sequence[Block] | Sequence[Operation],
        false_region: Region | Sequence[Block] | Sequence[Operation] | None = None,
    ):
        if false_region is None:
            false_region = Region()
        super().__init__(
            operands=[condition],
            regions=[true_region, false_region],
        )

    @staticmethod
    def parse_region_with_yield(parser: Parser) -> Region:
        region = parser.parse_region()
        block = region.blocks.last
        if block is None:
            block = Block()
            region.add_block(block)
        last_op = block.last_op
        if last_op is not None and last_op.has_trait(IsTerminator):
            return region
        block.add_op(YieldOp())
        return region

    @classmethod
    def parse(cls, parser: Parser) -> IfOp:
        condition = parser.parse_operand(ProjectionType())
        true_region = cls.parse_region_with_yield(parser)
        false_region = (
            cls.parse_region_with_yield(parser)
            if parser.parse_optional_keyword("else")
            else Region()
        )
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
        if bool(self.false_region.blocks):
            printer.print_string(" else ")
            printer.print_region(
                self.false_region,
                print_entry_block_args=False,
                print_block_terminators=True,
            )
        if bool(self.attributes.keys()):
            printer.print_attr_dict(self.attributes)


class FuncOpBase(IRDLOperation):
    """
    Base class for function operations.
    All function kinds share the same structure.
    """

    body = region_def()
    sym_name = prop_def(SymbolNameConstraint())
    function_type = prop_def(FunctionType)

    traits = traits_def(IsolatedFromAbove())

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
            function_type=(input_types, return_types),
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
        function_type: FunctionType | tuple[Sequence[Attribute], Sequence[Attribute]],
        body: Region | None = None,
    ):
        if isinstance(sym_name, str):
            sym_name = StringAttr(sym_name)
        if isinstance(function_type, tuple):
            function_type = FunctionType.from_lists(function_type[0], function_type[1])
        if body is None:
            body = Region()

        super().__init__(
            properties={
                "function_type": function_type,
                "sym_name": sym_name,
            },
            regions=[body],
        )


@irdl_op_definition
class PureOp(FuncOpBase):
    """
    Pure classical function operation.
    Classical computation only - no quantum operations allowed.
    """

    name = "proj.pure"


@irdl_op_definition
class UnitaryOp(FuncOpBase):
    """
    Unitary function operation.
    Quantum operations without measurement or allocation.
    """

    name = "proj.unitary"


@irdl_op_definition
class MixedOp(FuncOpBase):
    """
    Mixed quantum channel function operation.
    Full quantum operations including measurement and allocation.
    """

    name = "proj.mixed"


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
        YieldOp,
        IfOp,
        ReturnOp,
        PureOp,
        UnitaryOp,
        MixedOp,
    ],
    [
        BasisAttr,
        StateAttr,
        QubitType,
        ProjectionType,
    ],
)
