// RUN: XDSL_ROUNDTRIP
// RUN: XDSL_GENERIC_ROUNDTRIP

func.func @test_not(%arg0: !proj.projection) -> !proj.projection {
  // CHECK: %0 = proj.not %arg0
  // CHECK-GENERIC: %[[N0:.*]] = "proj.not"(%[[A0:.*]]) : (!proj.projection) -> !proj.projection
  %0 = proj.not %arg0
  func.return %0 : !proj.projection
}

func.func @test_and(%arg0: !proj.projection, %arg1: !proj.projection) -> !proj.projection {
  // CHECK: %0 = proj.and %arg0, %arg1
  // CHECK-GENERIC: %[[A0:.*]] = "proj.and"(%[[OP0:.*]], %[[OP1:.*]]) : (!proj.projection, !proj.projection) -> !proj.projection
  %0 = proj.and %arg0, %arg1
  func.return %0 : !proj.projection
}

func.func @test_or(%arg0: !proj.projection, %arg1: !proj.projection) -> !proj.projection {
  // CHECK: %0 = proj.or %arg0, %arg1
  // CHECK-GENERIC: %[[O0:.*]] = "proj.or"(%[[OP2:.*]], %[[OP3:.*]]) : (!proj.projection, !proj.projection) -> !proj.projection
  %0 = proj.or %arg0, %arg1
  func.return %0 : !proj.projection
}

func.func @test_xor(%arg0: !proj.projection, %arg1: !proj.projection) -> !proj.projection {
  // CHECK: %0 = proj.xor %arg0, %arg1
  // CHECK-GENERIC: %[[X0:.*]] = "proj.xor"(%[[OP4:.*]], %[[OP5:.*]]) : (!proj.projection, !proj.projection) -> !proj.projection
  %0 = proj.xor %arg0, %arg1
  func.return %0 : !proj.projection
}

func.func @test_from_bool(%arg0: i1) -> !proj.projection {
  // CHECK: %0 = proj.from_bool %arg0
  // CHECK-GENERIC: %[[F0:.*]] = "proj.from_bool"(%[[B0:.*]]) : (i1) -> !proj.projection
  %0 = proj.from_bool %arg0
  func.return %0 : !proj.projection
}

// Test proj.eq with different states
func.func @test_eq_zero(%arg0: !proj.qubit) -> !proj.projection {
  // CHECK: %0 = proj.eq %arg0, <zero> : !proj.qubit
  %0 = proj.eq %arg0, <zero> : !proj.qubit
  func.return %0 : !proj.projection
}

func.func @test_eq_plus(%arg0: !proj.qubit<x>) -> !proj.projection {
  // CHECK: %0 = proj.eq %arg0, <plus> : !proj.qubit<x>
  %0 = proj.eq %arg0, <plus> : !proj.qubit<x>
  func.return %0 : !proj.projection
}

// CHECK: proj.phase %angle
%angle = angle.zero
proj.phase %angle
