// RUN: xdsl-opt %s -p hoist-from-qif | filecheck %s

// Test: Pull out angle constants
// CHECK-LABEL: proj.unitary @test_angle_const
// CHECK-NOT: proj.qif
// CHECK: %[[PI:.*]] = angle.pi
// CHECK: proj.qif
// CHECK-NEXT: proj.phase %[[PI]]
proj.unitary @test_angle_const(%arg0: !proj.projection, %q: !proj.qubit) {
  proj.qif %arg0 {
    %pi = angle.pi
    proj.phase %pi
  }
  proj.return
}

// Test: Pull out projection operations
// CHECK-LABEL: proj.unitary @test_proj_ops
// CHECK-NOT: proj.qif
// CHECK: %[[EQ:.*]] = proj.eq %q : !proj.qubit, #proj.state<zero>
// CHECK: %[[EQ2:.*]] = proj.eq %q : !proj.qubit, #proj.state<one>
// CHECK: %[[AND:.*]] = proj.and %[[EQ]], %[[EQ2]]
// CHECK: proj.qif
proj.unitary @test_proj_ops(%q: !proj.qubit) {
  %arg0 = proj.eq %q : !proj.qubit, #proj.state<zero>
  proj.qif %arg0 {
    %eq2 = proj.eq %q : !proj.qubit, #proj.state<one>
    %and = proj.and %arg0, %eq2
    %pi = angle.pi
    proj.phase %pi
  }
  proj.return
}

// Test: Pull out operations with dependencies
// CHECK-LABEL: proj.unitary @test_deps
// CHECK-NOT: proj.qif
// CHECK: %[[PI:.*]] = angle.pi
// CHECK: %[[DOUBLE:.*]] = angle.scalar_mult 2.000000e+00, %[[PI]]
// CHECK: proj.qif
proj.unitary @test_deps(%arg0: !proj.projection, %q: !proj.qubit) {
  proj.qif %arg0 {
    %pi = angle.pi
    %double = angle.scalar_mult 2.0, %pi
    proj.phase %double
  }
  proj.return
}

// Test: Pull out from both true and else regions
// CHECK-LABEL: proj.unitary @test_else
// CHECK-NOT: proj.qif
// CHECK: %[[PI:.*]] = angle.pi
// CHECK: %[[ZERO:.*]] = angle.zero
// CHECK: proj.qif
// CHECK-NEXT: proj.phase %[[PI]]
// CHECK-NEXT: } else {
// CHECK-NEXT: proj.phase %[[ZERO]]
proj.unitary @test_else(%arg0: !proj.projection, %q: !proj.qubit) {
  proj.qif %arg0 {
    %pi = angle.pi
    proj.phase %pi
  } else {
    %zero = angle.zero
    proj.phase %zero
  }
  proj.return
}

// Test: Don't pull out quantum operations
// CHECK-LABEL: proj.unitary @test_quantum
// CHECK: proj.qif
// CHECK-NEXT: proj.qif
// CHECK-NEXT: proj.phase
proj.unitary @test_quantum(%arg0: !proj.projection, %q: !proj.qubit) {
  proj.qif %arg0 {
    %pi = angle.pi
    proj.qif %arg0 {
      proj.phase %pi
    }
  }
  proj.return
}

// Test: Pull out and operations
// CHECK-LABEL: proj.unitary @test_and
// CHECK-NOT: proj.qif
// CHECK: %[[AND:.*]] = proj.and %arg0, %arg1
// CHECK: proj.qif
proj.unitary @test_and(%arg0: !proj.projection, %arg1: !proj.projection, %q: !proj.qubit) {
  proj.qif %arg0 {
    %and = proj.and %arg0, %arg1
    %pi = angle.pi
    proj.phase %pi
  }
  proj.return
}
