// RUN: xdsl-opt %s --verify-diagnostics --split-input-file | filecheck %s

// Test proj.pure function verification - argument type mismatch
"proj.pure"() <{sym_name = "arg_mismatch", function_type = (i1) -> ()}> ({
  // CHECK: Expected entry block argument types to match function input types
  ^bb0(%b: !proj.projection):
    "proj.return"() : () -> ()
}) : () -> ()

// -----

// Test proj.unitary function verification - argument type mismatch
"proj.unitary"() <{sym_name = "arg_mismatch", function_type = (i1) -> ()}> ({
  // CHECK: Expected entry block argument types to match function input types
  ^bb0(%b: !proj.projection):
    "proj.return"() : () -> ()
}) : () -> ()

// -----

// Test proj.mixed function verification - argument type mismatch
"proj.mixed"() <{sym_name = "arg_mismatch", function_type = (i1) -> ()}> ({
  // CHECK: Expected entry block argument types to match function input types
  ^bb0(%b: !proj.projection):
    "proj.return"() : () -> ()
}) : () -> ()

// -----

// Test proj.pure function verification - return type mismatch
"proj.pure"() <{sym_name = "return_mismatch", function_type = () -> ()}> ({
  ^bb0():
    %0 = "arith.constant"() <{value = 1 : i1}> : () -> i1
    "proj.return"(%0) : (i1) -> ()
  // CHECK: Expected arguments to have the same types as the function output types: expected [], got [i1]
}) : () -> ()

// -----

// Test proj.unitary function verification - return type mismatch
"proj.unitary"() <{sym_name = "return_mismatch", function_type = () -> ()}> ({
  ^bb0():
    %0 = "proj.alloc"() <{state = #proj.state<zero>}> : () -> !proj.qubit
    "proj.return"(%0) : (!proj.qubit) -> ()
  // CHECK: Expected arguments to have the same types as the function output types: expected [], got [!proj.qubit]
}) : () -> ()

// -----

// Test proj.mixed function verification - return type mismatch (missing return)
"proj.mixed"() <{sym_name = "return_mismatch", function_type = () -> i1}> ({
  ^bb0():
    "proj.return"() : () -> ()
  // CHECK: Expected arguments to have the same types as the function output types: expected [i1], got []
}) : () -> ()

// -----

// Test proj.mixed function verification - return type mismatch (wrong type)
"proj.mixed"() <{sym_name = "return_mismatch", function_type = () -> i1}> ({
  ^bb0():
    %0 = "proj.alloc"() <{state = #proj.state<zero>}> : () -> !proj.qubit
    "proj.return"(%0) : (!proj.qubit) -> ()
  // CHECK: Expected arguments to have the same types as the function output types: expected [i1], got [!proj.qubit]
}) : () -> ()
