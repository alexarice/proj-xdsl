// Test function inlining pass for proj-xdsl

// RUN: xdsl-opt %s -p func-inline | filecheck %s

// Test 1: Simple pure function inlining
// CHECK-LABEL: proj.pure @simple_callee
proj.pure @simple_callee(%x: i1) -> i1 {
  %0 = arith.andi %x, %x : i1
  proj.return %0 : i1
}

// CHECK-LABEL: proj.pure @simple_caller
// CHECK-NOT: proj.call
// CHECK: %[[CONST:.*]] = arith.constant true
// CHECK: %[[RESULT:.*]] = arith.andi %[[CONST]], %[[CONST]] : i1
// CHECK: proj.return %[[RESULT]] : i1
proj.pure @simple_caller() -> i1 {
  %0 = arith.constant true
  %1 = proj.call @simple_callee(%0) : (i1) -> i1
  proj.return %1 : i1
}

// Test 2: Void function inlining
// CHECK-LABEL: proj.pure @void_callee
proj.pure @void_callee() {
  proj.return
}

// CHECK-LABEL: proj.pure @void_caller
// CHECK-NOT: proj.call
// CHECK: proj.return
proj.pure @void_caller() {
  proj.call @void_callee() : () -> ()
  proj.return
}

// Test 3: Unitary function with quantum operations
// CHECK-LABEL: proj.unitary @phase_callee
proj.unitary @phase_callee(%q: !proj.qubit) {
  %0 = angle.pi
  proj.phase %0
  proj.return
}

// CHECK-LABEL: proj.unitary @phase_caller
// CHECK-NOT: proj.call
// CHECK: %[[PI:.*]] = angle.pi
// CHECK: proj.phase %[[PI]]
// CHECK: proj.return
proj.unitary @phase_caller(%q: !proj.qubit) {
  proj.call @phase_callee(%q) : (!proj.qubit) -> ()
  proj.return
}

// Test 4: Multiple arguments
// CHECK-LABEL: proj.pure @multi_arg_callee
proj.pure @multi_arg_callee(%a: i1, %b: i1) -> i1 {
  %0 = arith.andi %a, %b : i1
  proj.return %0 : i1
}

// CHECK-LABEL: proj.pure @multi_arg_caller
// CHECK-NOT: proj.call
// CHECK: %[[A:.*]] = arith.constant true
// CHECK: %[[B:.*]] = arith.constant false
// CHECK: %[[RESULT:.*]] = arith.andi %[[A]], %[[B]] : i1
// CHECK: proj.return %[[RESULT]] : i1
proj.pure @multi_arg_caller() -> i1 {
  %0 = arith.constant true
  %1 = arith.constant false
  %2 = proj.call @multi_arg_callee(%0, %1) : (i1, i1) -> i1
  proj.return %2 : i1
}

// Test 5: Sequential function calls
// CHECK-LABEL: proj.pure @identity
proj.pure @identity(%x: i1) -> i1 {
  proj.return %x : i1
}

// CHECK-LABEL: proj.pure @nested_caller
// CHECK-NOT: proj.call
proj.pure @sequential_caller() -> i1 {
  %0 = arith.constant true
  %1 = proj.call @identity(%0) : (i1) -> i1
  %2 = proj.call @identity(%1) : (i1) -> i1
  proj.return %2 : i1
}
