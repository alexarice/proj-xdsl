// RUN: xdsl-opt %s -p canonicalize | filecheck %s

// Test: Remove empty qif with only true region
// CHECK-LABEL: func.func @test_empty_true
// CHECK-NOT: proj.qif
func.func @test_empty_true(%arg0: !proj.projection) {
  proj.qif %arg0 {
  }
  func.return
}

// Test: Remove empty qif with both regions
// CHECK-LABEL: func.func @test_empty_both
// CHECK-NOT: proj.qif
func.func @test_empty_both(%arg0: !proj.projection) {
  proj.qif %arg0 {
  } else {
  }
  func.return
}

// Test: Don't remove qif with ops in true region
// CHECK-LABEL: func.func @test_nonempty_true
// CHECK: proj.qif %arg0 {
func.func @test_nonempty_true(%arg0: !proj.projection, %a: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a
  }
  func.return
}

// Test: Transform qif with empty true and non-empty false to negated condition
// CHECK-LABEL: func.func @test_nonempty_false
// CHECK: %[[NOT:.*]] = proj.not %arg0
// CHECK: proj.qif %[[NOT]] {
func.func @test_nonempty_false(%arg0: !proj.projection, %a: !angle.type) {
  proj.qif %arg0 {
  } else {
    proj.phase %a
  }
  func.return
}

// Test: Transform qif with empty true and non-empty false to negated condition
// CHECK-LABEL: func.func @test_empty_true_nonempty_false
// CHECK: %[[NOT:.*]] = proj.not %arg0
// CHECK: proj.qif %[[NOT]] {
func.func @test_empty_true_nonempty_false(%arg0: !proj.projection, %a: !angle.type) {
  proj.qif %arg0 {
  } else {
    proj.phase %a
  }
  func.return
}

// Test: Don't remove qif with non-empty true but empty false
// CHECK-LABEL: func.func @test_nonempty_true_empty_false
// CHECK: proj.qif %arg0 {
func.func @test_nonempty_true_empty_false(%arg0: !proj.projection, %a: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a
  } else {
  }
  func.return
}

// Test: Merge consecutive phase operations
// CHECK-LABEL: func.func @test_phase_merge
// CHECK: %[[SUM:.*]] = angle.add
// CHECK-NEXT: proj.phase %[[SUM]]
func.func @test_phase_merge(%arg0: !proj.projection, %a1: !angle.type, %a2: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
    proj.phase %a2
  }
  func.return
}

// Test: Hoist phase operations to the end (after angle ops, merged first)
// CHECK-LABEL: func.func @test_phase_hoist
// CHECK: %pi = angle.pi
// CHECK-NEXT: %pi2 = angle.pi
// CHECK-NEXT: %[[SUM:.*]] = angle.add
// CHECK-NEXT: proj.phase %[[SUM]]
func.func @test_phase_hoist(%arg0: !proj.projection, %a1: !angle.type, %a2: !angle.type) {
  proj.qif %arg0 {
    %pi = angle.pi
    proj.phase %a1
    %pi2 = angle.pi
    proj.phase %a2
  }
  func.return
}

// Test: Multiple consecutive phases should be merged into one
// CHECK-LABEL: func.func @test_phase_multi_merge
// CHECK: proj.qif %arg0 {
// CHECK: angle.add
// CHECK: proj.phase
// CHECK: func.return
func.func @test_phase_multi_merge(%arg0: !proj.projection, %a1: !angle.type, %a2: !angle.type, %a3: !angle.type, %a4: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
    proj.phase %a2
    proj.phase %a3
    proj.phase %a4
  }
  func.return
}

// Test: Phase should end up before the terminator
// CHECK-LABEL: func.func @test_phase_before_terminator
// CHECK: proj.phase
// CHECK: func.return
func.func @test_phase_before_terminator(%arg0: !proj.projection, %a1: !angle.type) {
  proj.qif %arg0 {
    proj.phase %a1
    %pi = angle.pi
  }
  func.return
}
