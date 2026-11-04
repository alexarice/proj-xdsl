// RUN: xdsl-opt %s --verify-diagnostics --split-input-file | filecheck %s

// Test proj.call - callee not found in symbol table
"builtin.module"() ({
  "proj.pure"() <{sym_name = "caller", function_type = () -> ()}> ({
  ^bb0():
    "proj.call"() <{callee = @nonexistent}> : () -> ()
    // CHECK: '@nonexistent' could not be found in symbol table
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - callee is not a function
"builtin.module"() ({
  "func.func"() <{sym_name = "not_a_func", function_type = () -> ()}> ({
  ^bb0():
    "func.return"() : () -> ()
  }) : () -> ()
  "proj.pure"() <{sym_name = "caller", function_type = () -> ()}> ({
  ^bb0():
    "proj.call"() <{callee = @not_a_func}> : () -> ()
    // CHECK: '@not_a_func' does not reference a valid function
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - incorrect number of operands
"builtin.module"() ({
  "proj.pure"() <{sym_name = "callee", function_type = (i1, i1) -> ()}> ({
  ^bb0(%a: i1, %b: i1):
    "proj.return"() : () -> ()
  }) : () -> ()
  "proj.pure"() <{sym_name = "caller", function_type = () -> ()}> ({
  ^bb0():
    %0 = "arith.constant"() <{value = 1 : i1}> : () -> i1
    "proj.call"(%0) <{callee = @callee}> : (i1) -> ()
    // CHECK: incorrect number of operands for callee: expected 2, got 1
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - incorrect number of results
"builtin.module"() ({
  "proj.pure"() <{sym_name = "callee", function_type = () -> (i1, i1)}> ({
  ^bb0():
    %0 = "arith.constant"() <{value = true}> : () -> i1
    %1 = "arith.constant"() <{value = false}> : () -> i1
    "proj.return"(%0, %1) : (i1, i1) -> ()
  }) : () -> ()
  "proj.pure"() <{sym_name = "caller", function_type = () -> ()}> ({
  ^bb0():
    "proj.call"() <{callee = @callee}> : () -> (i1)
    // CHECK: incorrect number of results for callee: expected 2, got 1
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - operand type mismatch
"builtin.module"() ({
  "proj.pure"() <{sym_name = "callee", function_type = (i1) -> ()}> ({
  ^bb0(%a: i1):
    "proj.return"() : () -> ()
  }) : () -> ()
  "proj.pure"() <{sym_name = "caller", function_type = () -> ()}> ({
  ^bb0():
    %0 = "test.op"() : () -> !proj.qubit
    "proj.call"(%0) <{callee = @callee}> : (!proj.qubit) -> ()
    // CHECK: operand type mismatch: expected operand type i1, but provided !proj.qubit for operand number 0
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - result type mismatch
"builtin.module"() ({
  "proj.pure"() <{sym_name = "callee", function_type = () -> (i1)}> ({
  ^bb0():
    %0 = "arith.constant"() <{value = 1 : i1}> : () -> i1
    "proj.return"(%0) : (i1) -> ()
  }) : () -> ()
  "proj.pure"() <{sym_name = "caller", function_type = () -> ()}> ({
  ^bb0():
    "proj.call"() <{callee = @callee}> : () -> (!proj.projection)
    // CHECK: result type mismatch: expected result type i1, but provided !proj.projection for result number 0
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - pure calling mixed (not allowed)
"builtin.module"() ({
  "proj.mixed"() <{sym_name = "mixed_func", function_type = () -> ()}> ({
  ^bb0():
    "proj.return"() : () -> ()
  }) : () -> ()
  "proj.pure"() <{sym_name = "pure_caller", function_type = () -> ()}> ({
  ^bb0():
    "proj.call"() <{callee = @mixed_func}> : () -> ()
    // CHECK: Cannot call mixed function from pure function
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - pure calling unitary (not allowed)
"builtin.module"() ({
  "proj.unitary"() <{sym_name = "unitary_func", function_type = () -> ()}> ({
  ^bb0():
    "proj.return"() : () -> ()
  }) : () -> ()
  "proj.pure"() <{sym_name = "pure_caller", function_type = () -> ()}> ({
  ^bb0():
    "proj.call"() <{callee = @unitary_func}> : () -> ()
    // CHECK: Cannot call unitary function from pure function
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

// -----

// Test proj.call - unitary calling mixed (not allowed)
"builtin.module"() ({
  "proj.mixed"() <{sym_name = "mixed_func", function_type = () -> ()}> ({
  ^bb0():
    "proj.return"() : () -> ()
  }) : () -> ()
  "proj.unitary"() <{sym_name = "unitary_caller", function_type = () -> ()}> ({
  ^bb0():
    "proj.call"() <{callee = @mixed_func}> : () -> ()
    // CHECK: Cannot call mixed function from unitary function
    "proj.return"() : () -> ()
  }) : () -> ()
}) : () -> ()
