// RUN: XDSL_ROUNDTRIP
// RUN: XDSL_GENERIC_ROUNDTRIP

func.func @test_not_proj(%arg0: !proj.projection) -> !proj.projection {
  // CHECK: %0 = proj.not %arg0 : !proj.projection
  // CHECK-GENERIC: %[[N0:.*]] = "proj.not"(%[[A0:.*]]) : (!proj.projection) -> !proj.projection
  %0 = proj.not %arg0 : !proj.projection
  func.return %0 : !proj.projection
}

func.func @test_not_bool(%arg0: i1) -> i1 {
  // CHECK: %0 = proj.not %arg0 : i1
  // CHECK-GENERIC: %[[N1:.*]] = "proj.not"(%[[A1:.*]]) : (i1) -> i1
  %0 = proj.not %arg0 : i1
  func.return %0 : i1
}

func.func @test_and_proj(%arg0: !proj.projection, %arg1: !proj.projection) -> !proj.projection {
  // CHECK: %0 = proj.and %arg0, %arg1 : !proj.projection
  // CHECK-GENERIC: %[[A0:.*]] = "proj.and"(%[[OP0:.*]], %[[OP1:.*]]) : (!proj.projection, !proj.projection) -> !proj.projection
  %0 = proj.and %arg0, %arg1 : !proj.projection
  func.return %0 : !proj.projection
}

func.func @test_and_bool(%arg0: i1, %arg1: i1) -> i1 {
  // CHECK: %0 = proj.and %arg0, %arg1 : i1
  // CHECK-GENERIC: %[[B0:.*]] = "proj.and"(%[[OP2:.*]], %[[OP3:.*]]) : (i1, i1) -> i1
  %0 = proj.and %arg0, %arg1 : i1
  func.return %0 : i1
}
