// RUN: xdsl-opt %s -p canonicalize | filecheck %s

// Test: 0 * angle = 0
// CHECK-LABEL: func.func @test_zero_mult
// CHECK: %zero = angle.zero
// CHECK: func.return %zero
func.func @test_zero_mult(%arg0: !angle.type) -> !angle.type {
  %zero = angle.scalar_mult 0.0, %arg0
  func.return %zero : !angle.type
}

// Test: 1.0 * angle = angle (folded)
// CHECK-LABEL: func.func @test_one_mult
// CHECK-NOT: angle.scalar_mult
// CHECK: func.return %arg0
func.func @test_one_mult(%arg0: !angle.type) -> !angle.type {
  %result = angle.scalar_mult 1.0, %arg0
  func.return %result : !angle.type
}

// Test: non-zero, non-one scalar mult is not changed
// CHECK-LABEL: func.func @test_other_mult
// CHECK: angle.scalar_mult 2.0
// CHECK: func.return
func.func @test_other_mult(%arg0: !angle.type) -> !angle.type {
  %result = angle.scalar_mult 2.0, %arg0
  func.return %result : !angle.type
}

// Test: combine nested scalar multiplications: a * (b * angle) = (a * b) * angle
// CHECK-LABEL: func.func @test_combine
// CHECK: angle.scalar_mult 6.0
// CHECK: func.return
func.func @test_combine(%arg0: !angle.type) -> !angle.type {
  %inner = angle.scalar_mult 2.0, %arg0
  %outer = angle.scalar_mult 3.0, %inner
  func.return %outer : !angle.type
}

// Test: fold 1.0 * angle combined with scalar mult combine
// CHECK-LABEL: func.func @test_combine_with_fold
// CHECK: angle.scalar_mult 6.0
// CHECK: func.return
func.func @test_combine_with_fold(%arg0: !angle.type) -> !angle.type {
  %inner = angle.scalar_mult 2.0, %arg0
  %outer = angle.scalar_mult 3.0, %inner
  %result = angle.scalar_mult 1.0, %outer
  func.return %result : !angle.type
}

// Test: 0.5 * (2.0 * angle) = 1.0 * angle -> angle (combine + fold)
// CHECK-LABEL: func.func @test_combine_to_one
// CHECK: func.return %arg0
func.func @test_combine_to_one(%arg0: !angle.type) -> !angle.type {
  %inner = angle.scalar_mult 2.0, %arg0
  %outer = angle.scalar_mult 0.5, %inner
  func.return %outer : !angle.type
}
