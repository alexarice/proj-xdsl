// RUN: xdsl-opt %s -p split-qif | filecheck %s

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

// Don't split classical ops only
// CHECK-LABEL: proj.unitary @test_classical
// CHECK: proj.qif %arg0 {
// CHECK: proj.and
// CHECK-NOT: proj.qif
proj.unitary @test_classical(%arg0: !proj.projection, %arg1: !proj.projection) {
  proj.qif %arg0 {
    %and = proj.and %arg0, %arg1
  }
  proj.return
}

// Don't split mixed classical and quantum ops
// CHECK-LABEL: proj.unitary @test_mixed_ops
// CHECK: proj.qif %arg0 {
// CHECK: angle.pi
// CHECK: proj.phase
// CHECK-NOT: proj.qif
proj.unitary @test_mixed_ops(%arg0: !proj.projection) {
  proj.qif %arg0 {
    %pi = angle.pi
    proj.phase %pi
  }
  proj.return
}

// Don't split else with classical ops
// CHECK-LABEL: proj.unitary @test_else_classical
// CHECK: proj.qif %arg0 {
// CHECK: proj.phase
// CHECK: } else {
// CHECK: proj.and
// CHECK-NOT: proj.qif
proj.unitary @test_else_classical(%arg0: !proj.projection, %arg1: !proj.projection, %a1: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
  } else {
    %and = proj.and %arg0, %arg1
  }
  proj.return
}
