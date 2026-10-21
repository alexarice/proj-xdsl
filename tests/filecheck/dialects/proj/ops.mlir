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

func.func @test_from_bool(%arg0: i1) -> !proj.projection {
  // CHECK: %0 = proj.from_bool %arg0
  // CHECK-GENERIC: %[[F0:.*]] = "proj.from_bool"(%[[B0:.*]]) : (i1) -> !proj.projection
  %0 = proj.from_bool %arg0
  func.return %0 : !proj.projection
}
