"""Projection dialect operations."""

from __future__ import annotations

from collections.abc import Sequence
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
    parse_func_op_like,
    print_func_op_like,
)
from xdsl.interfaces import HasCanonicalizationPatternsInterface
from xdsl.ir import (
    Attribute,
    Block,
    Operation,
    OpTrait,
    Region,
    SSAValue,
    VerifyException,
)
from xdsl.irdl import (
    IRDLOperation,
    irdl_op_definition,
    irdl_to_attr_constraint,
    operand_def,
    prop_def,
    region_def,
    result_def,
    traits_def,
    var_operand_def,
    var_result_def,
)
from xdsl.parser import Parser
from xdsl.pattern_rewriter import RewritePattern
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

from projxdsl.dialects.angle.ops import AngleType
from projxdsl.dialects.proj.attrs import StateAttr
from projxdsl.dialects.proj.types import ProjectionType, QubitType
from projxdsl.func_kind import FuncKind


class FuncOpBase(IRDLOperation):
    """
    Base class for function operations. All function kinds share the same structure.
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
        """Initialize the trait with a minimum required function kind."""
        self.min_kind = min_kind

    def verify(self, op: Operation) -> None:
        """Verify that the operation appears only in allowed function kinds."""
        func_op = op.parent_op()
        while func_op is not None and not isinstance(func_op, FuncOpBase):
            func_op = func_op.parent_op()

        if func_op is None:
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
    """Negation operation for projections."""

    name = "proj.not"

    input = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$input attr-dict"

    def __init__(self, input: SSAValue):
        super().__init__(operands=[input], result_types=[ProjectionType()])


@irdl_op_definition
class AndOp(IRDLOperation):
    """Conjunction operation for projections."""

    name = "proj.and"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class OrOp(IRDLOperation):
    """Disjunction operation for projections."""

    name = "proj.or"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class XorOp(IRDLOperation):
    """Exclusive-or operation for projections."""

    name = "proj.xor"

    lhs = operand_def(ProjectionType)
    rhs = operand_def(ProjectionType)
    result = result_def(ProjectionType)

    assembly_format = "$lhs `,` $rhs attr-dict"

    def __init__(self, lhs: SSAValue, rhs: SSAValue):
        super().__init__(operands=[lhs, rhs], result_types=[ProjectionType()])


@irdl_op_definition
class FromBoolOp(IRDLOperation):
    """Cast operation from boolean to projection."""

    name = "proj.from_bool"

    input = operand_def(i1)
    result = result_def(ProjectionType)

    assembly_format = "$input attr-dict"

    def __init__(self, input: SSAValue):
        super().__init__(operands=[input], result_types=[ProjectionType()])


@irdl_op_definition
class AllocOp(IRDLOperation):
    """Qubit allocation operation. Only allowed in mixed functions."""

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
    """Projection creation operation by comparing a qubit to a ket state."""

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
class PhaseOp(IRDLOperation, HasCanonicalizationPatternsInterface):
    """Phase operation. Only allowed in unitary and mixed functions."""

    name = "proj.phase"

    angle = operand_def(AngleType)

    traits = traits_def(AllowedInFuncKinds(FuncKind.UNITARY))

    assembly_format = "$angle attr-dict"

    def __init__(self, angle: SSAValue):
        super().__init__(operands=[angle])

    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from projxdsl.dialects.proj.canonicalize import HoistAndMergePhasePattern

        return (HoistAndMergePhasePattern(),)


@irdl_op_definition
class MeasureOp(IRDLOperation):
    """Measurement operation. Only allowed in mixed functions."""

    name = "proj.measure"

    projection = operand_def(ProjectionType)
    result = result_def(i1)

    traits = traits_def(AllowedInFuncKinds(FuncKind.MIXED))

    assembly_format = "$projection attr-dict"

    def __init__(self, projection: SSAValue):
        super().__init__(operands=[projection], result_types=[i1])


@irdl_op_definition
class QifOp(IRDLOperation, HasCanonicalizationPatternsInterface):
    """Quantum if operation for projections."""

    name = "proj.qif"

    condition = operand_def(ProjectionType)
    true_region = region_def("single_block")
    false_region = region_def()

    traits = traits_def(
        NoTerminator(),
        AllowedInFuncKinds(FuncKind.UNITARY),
    )

    def __init__(
        self,
        condition: SSAValue,
        true_region: Region | Block,
        false_region: Region | Block | None = None,
    ):
        if isinstance(true_region, Block):
            true_region = Region(true_region)
        if false_region is None:
            false_region = Region()
        if isinstance(false_region, Block):
            false_region = Region(false_region)
        super().__init__(
            operands=[condition],
            regions=[true_region, false_region],
        )

    def verify_(self) -> None:
        # Verify false_region has at most one block
        if len(self.false_region.blocks) > 1:
            raise VerifyException("'false_region' must have at most one block")

    @classmethod
    def parse(cls, parser: Parser) -> QifOp:
        condition = parser.parse_operand(ProjectionType())
        true_region = parser.parse_region()
        if not true_region.blocks:
            true_region.add_block(Block())
        if parser.parse_optional_keyword("else"):
            false_region = parser.parse_region()
            if not false_region.blocks:
                false_region.add_block(Block())
        else:
            false_region = Region()
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

    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from projxdsl.dialects.proj.canonicalize import (
            RemoveEmptyQifElsePattern,
            RemoveEmptyQifPattern,
            SwapEmptyThenWithElsePattern,
        )

        return (
            SwapEmptyThenWithElsePattern(),
            RemoveEmptyQifElsePattern(),
            RemoveEmptyQifPattern(),
        )


@irdl_op_definition
class PureOp(FuncOpBase):
    """Pure classical function operation."""

    name = "proj.pure"

    FUNC_KIND: ClassVar = FuncKind.PURE


@irdl_op_definition
class UnitaryOp(FuncOpBase):
    """Unitary function operation."""

    name = "proj.unitary"

    FUNC_KIND: ClassVar = FuncKind.UNITARY


@irdl_op_definition
class MixedOp(FuncOpBase):
    """Mixed quantum channel function operation."""

    name = "proj.mixed"

    FUNC_KIND: ClassVar = FuncKind.MIXED


@irdl_op_definition
class ReturnOp(IRDLOperation):
    """Return operation for function operations."""

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
        assert isinstance(op, CallOp)

        found_callee = SymbolTable.lookup_symbol(op, op.callee)
        if not found_callee:
            raise VerifyException(f"'{op.callee}' could not be found in symbol table")

        if not isinstance(found_callee, FuncOpBase):
            raise VerifyException(f"'{op.callee}' does not reference a valid function")

        caller_func = op.parent_op()
        while caller_func is not None and not isinstance(caller_func, FuncOpBase):
            caller_func = caller_func.parent_op()

        if caller_func is not None:
            callee_kind = found_callee.FUNC_KIND
            caller_kind = caller_func.FUNC_KIND

            if callee_kind > caller_kind:
                raise VerifyException(
                    f"Cannot call {callee_kind.display_name} function from "
                    f"{caller_kind.display_name} function. "
                    f"{caller_kind.display_name} functions can only call functions "
                    "of equal or lower privilege level."
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
    """Function call operation."""

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
