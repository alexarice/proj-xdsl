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
