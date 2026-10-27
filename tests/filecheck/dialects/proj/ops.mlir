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

// Test proj.if with true region
func.func @test_if(%arg0: !proj.projection) {
  // CHECK: proj.if %arg0 {
  // CHECK-GENERIC: "proj.if"(%[[ARG0:.*]]) ({
  // CHECK-GENERIC:   "proj.yield"() : () -> ()
  // CHECK-GENERIC: }) : (!proj.projection) -> ()
  proj.if %arg0 {
    proj.yield
  }
  func.return
}

// Test proj.if with else region
func.func @test_if_else(%arg0: !proj.projection) {
  // CHECK: proj.if %arg0 {
  // CHECK:   proj.yield
  // CHECK: } else {
  // CHECK:   proj.yield
  // CHECK: }
  // CHECK-GENERIC: "proj.if"(%[[ARG0:.*]]) ({
  // CHECK-GENERIC:   "proj.yield"() : () -> ()
  // CHECK-GENERIC: }, {
  // CHECK-GENERIC:   "proj.yield"() : () -> ()
  // CHECK-GENERIC: }) : (!proj.projection) -> ()
  proj.if %arg0 {
    proj.yield
  } else {
    proj.yield
  }
  func.return
}

// Test proj.alloc with different states
func.func @test_alloc() {
  // CHECK: %[[Q0:.*]] = proj.alloc<zero> : !proj.qubit
  // CHECK-GENERIC: %[[Q0:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<zero>{{.*}}> : () -> !proj.qubit
  %q0 = proj.alloc <zero> : !proj.qubit
  // CHECK: %[[Q1:.*]] = proj.alloc<one> : !proj.qubit
  // CHECK-GENERIC: %[[Q1:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<one>{{.*}}> : () -> !proj.qubit
  %q1 = proj.alloc <one> : !proj.qubit
  // CHECK: %[[QP:.*]] = proj.alloc<plus> : !proj.qubit
  // CHECK-GENERIC: %[[QP:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<plus>{{.*}}> : () -> !proj.qubit
  %q_plus = proj.alloc <plus> : !proj.qubit
  // CHECK: %[[QM:.*]] = proj.alloc<minus> : !proj.qubit
  // CHECK-GENERIC: %[[QM:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<minus>{{.*}}> : () -> !proj.qubit
  %q_minus = proj.alloc <minus> : !proj.qubit
  // CHECK: %[[QL:.*]] = proj.alloc<left> : !proj.qubit
  // CHECK-GENERIC: %[[QL:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<left>{{.*}}> : () -> !proj.qubit
  %q_left = proj.alloc <left> : !proj.qubit
  // CHECK: %[[QR:.*]] = proj.alloc<right> : !proj.qubit
  // CHECK-GENERIC: %[[QR:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<right>{{.*}}> : () -> !proj.qubit
  %q_right = proj.alloc <right> : !proj.qubit
  func.return
}
