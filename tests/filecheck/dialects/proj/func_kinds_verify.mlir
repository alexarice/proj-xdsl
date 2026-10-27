// RUN: xdsl-opt %s --verify-diagnostics --split-input-file | filecheck %s

// Test that alloc is not allowed in pure functions
"proj.pure"() <{sym_name = "pure_with_alloc", function_type = () -> ()}> ({
  ^bb0():
    %0 = "proj.alloc"() <{state = #proj.state<zero>}> : () -> !proj.qubit
    "proj.return"() : () -> ()
  // CHECK: Operation 'proj.alloc' is not allowed in proj.pure functions. Allowed in: proj.mixed
}) : () -> ()

// -----

// Test that alloc is not allowed in unitary functions
"proj.unitary"() <{sym_name = "unitary_with_alloc", function_type = () -> ()}> ({
  ^bb0():
    %0 = "proj.alloc"() <{state = #proj.state<zero>}> : () -> !proj.qubit
    "proj.return"() : () -> ()
  // CHECK: Operation 'proj.alloc' is not allowed in proj.unitary functions. Allowed in: proj.mixed
}) : () -> ()

// -----

// Test that measure is not allowed in pure functions
"proj.pure"() <{sym_name = "pure_with_measure", function_type = () -> ()}> ({
  ^bb0():
    %0 = "arith.constant"() <{value = 1 : i1}> : () -> i1
    %1 = "proj.from_bool"(%0) : (i1) -> !proj.projection
    %2 = "proj.measure"(%1) : (!proj.projection) -> i1
    "proj.return"() : () -> ()
  // CHECK: Operation 'proj.measure' is not allowed in proj.pure functions. Allowed in: proj.mixed
}) : () -> ()

// -----

// Test that measure is not allowed in unitary functions
"proj.unitary"() <{sym_name = "unitary_with_measure", function_type = () -> ()}> ({
  ^bb0():
    %0 = "arith.constant"() <{value = 1 : i1}> : () -> i1
    %1 = "proj.from_bool"(%0) : (i1) -> !proj.projection
    %2 = "proj.measure"(%1) : (!proj.projection) -> i1
    "proj.return"() : () -> ()
  // CHECK: Operation 'proj.measure' is not allowed in proj.unitary functions. Allowed in: proj.mixed
}) : () -> ()

// -----

// Test that if is not allowed in pure functions
"proj.pure"() <{sym_name = "pure_with_if", function_type = () -> ()}> ({
  ^bb0():
    %0 = "arith.constant"() <{value = 1 : i1}> : () -> i1
    %1 = "proj.from_bool"(%0) : (i1) -> !proj.projection
    "proj.if"(%1) ({
      "proj.yield"() : () -> ()
    }, {
      "proj.yield"() : () -> ()
    }) : (!proj.projection) -> ()
    "proj.return"() : () -> ()
  // CHECK: Operation 'proj.if' is not allowed in proj.pure functions. Allowed in: proj.unitary or proj.mixed
}) : () -> ()

// -----

// Test that phase is not allowed in pure functions
"proj.pure"() <{sym_name = "pure_with_phase", function_type = () -> ()}> ({
  ^bb0():
    %0 = "angle.zero"() : () -> !angle.type
    "proj.phase"(%0) : (!angle.type) -> ()
    "proj.return"() : () -> ()
  // CHECK: Operation 'proj.phase' is not allowed in proj.pure functions. Allowed in: proj.unitary or proj.mixed
}) : () -> ()
