// RUN: xdsl-opt %s -p canonicalize | filecheck %s

// Test: 0 * angle = 0
// CHECK-LABEL: func.func @test_zero_mult
// CHECK: %zero = angle.zero
func.func @test_zero_mult(%arg0: !angle.type) {
  %zero = angle.scalar_mult 0.0, %arg0
  func.return
}

// Test: 1.0 * angle = angle (folded)
// CHECK-LABEL: func.func @test_one_mult
// CHECK-NOT: angle.scalar_mult
func.func @test_one_mult(%arg0: !angle.type) {
  %result = angle.scalar_mult 1.0, %arg0
  func.return
}

// Test: non-zero, non-one scalar mult is not changed
// CHECK-LABEL: func.func @test_other_mult
// CHECK: angle.scalar_mult 2.0
func.func @test_other_mult(%arg0: !angle.type) {
  %result = angle.scalar_mult 2.0, %arg0
  func.return
}
