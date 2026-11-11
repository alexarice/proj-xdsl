// RUN: xdsl-opt %s -p "simplify-qif,canonicalize" | filecheck %s

// Split qif with else region
// CHECK-LABEL: proj.unitary @test_else_split
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %a1
// CHECK-NEXT: }
// CHECK: %[[NOT:.*]] = proj.not %arg0
// CHECK-NEXT: proj.qif %[[NOT]] {
// CHECK-NEXT: proj.phase %a2
// CHECK-NEXT: }
proj.unitary @test_else_split(%arg0: !proj.projection, %a1: !angle.type, %a2: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
  } else {
    proj.phase %a2
  }
  proj.return
}

// Split qif with multiple ops (no else)
// CHECK-LABEL: proj.unitary @test_multi_ops
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %a1
// CHECK-NEXT: }
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %a2
// CHECK-NEXT: }
proj.unitary @test_multi_ops(%arg0: !proj.projection, %a1: !angle.type, %a2: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
    proj.phase %a2
  }
  proj.return
}

// Don't split single op (no else)
// CHECK-LABEL: proj.unitary @test_single
// CHECK: proj.qif %arg0 {
// CHECK: proj.phase
proj.unitary @test_single(%arg0: !proj.projection, %a1: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
  }
  proj.return
}

// Split qif with else and multiple ops
// CHECK-LABEL: proj.unitary @test_else_multi
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %a1
// CHECK-NEXT: }
// CHECK-NEXT: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %a2
// CHECK-NEXT: }
// CHECK: %[[NOT:.*]] = proj.not %arg0
// CHECK-NEXT: proj.qif %[[NOT]] {
// CHECK-NEXT: proj.phase %a3
// CHECK-NEXT: }
// CHECK-NEXT: proj.qif %[[NOT]] {
// CHECK-NEXT: proj.phase %a4
// CHECK-NEXT: }
proj.unitary @test_else_multi(%arg0: !proj.projection, %a1: !angle.type, %a2: !angle.type, %a3: !angle.type, %a4: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
    proj.phase %a2
  } else {
    proj.phase %a3
    proj.phase %a4
  }
  proj.return
}

// Hoist classical ops (empty qif removed)
// CHECK-LABEL: proj.unitary @test_classical
// CHECK: %[[AND:.*]] = proj.and %arg0, %arg1
// CHECK-NOT: proj.qif
// CHECK: proj.return
proj.unitary @test_classical(%arg0: !proj.projection, %arg1: !proj.projection) {
  proj.qif %arg0 {
    %and = proj.and %arg0, %arg1
  }
  proj.return
}

// Hoist classical from mixed ops
// CHECK-LABEL: proj.unitary @test_mixed_ops
// CHECK: %[[PI:.*]] = angle.pi
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %[[PI]]
// CHECK-NEXT: }
// CHECK: proj.return
proj.unitary @test_mixed_ops(%arg0: !proj.projection) {
  proj.qif %arg0 {
    %pi = angle.pi
    proj.phase %pi
  }
  proj.return
}

// Split else and hoist classical (empty qif removed)
// CHECK-LABEL: proj.unitary @test_else_classical
// CHECK: %[[AND:.*]] = proj.and %arg0, %arg1
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %a1
// CHECK-NEXT: }
// CHECK: %[[NOT:.*]] = proj.not %arg0
// CHECK-NOT: proj.qif %[[NOT]]
proj.unitary @test_else_classical(%arg0: !proj.projection, %arg1: !proj.projection, %a1: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
  } else {
    %and = proj.and %arg0, %arg1
  }
  proj.return
}

// Hoist classical ops from qif
// CHECK-LABEL: proj.unitary @test_hoist
// CHECK: %[[PI:.*]] = angle.pi
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %[[PI]]
// CHECK-NEXT: }
proj.unitary @test_hoist(%arg0: !proj.projection) {
  proj.qif %arg0 {
    %pi = angle.pi
    proj.phase %pi
  }
  proj.return
}

// Split qif/else (angles already hoisted)
// CHECK-LABEL: proj.unitary @test_split_and_hoist
// CHECK: proj.qif %arg0 {
// CHECK-NEXT: proj.phase %pi1
// CHECK-NEXT: }
// CHECK: %[[NOT:.*]] = proj.not %arg0
// CHECK-NEXT: proj.qif %[[NOT]] {
// CHECK-NEXT: proj.phase %pi2
proj.unitary @test_split_and_hoist(%arg0: !proj.projection, %pi1: !angle.type, %pi2: !angle.type) {
  proj.qif %arg0 {
    proj.phase %pi1
  } else {
    proj.phase %pi2
  }
  proj.return
}
