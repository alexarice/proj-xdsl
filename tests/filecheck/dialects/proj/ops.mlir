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
  // CHECK: %0 = proj.eq %arg0 : !proj.qubit, #proj.state<zero>
  %0 = proj.eq %arg0 : !proj.qubit, #proj.state<zero>
  func.return %0 : !proj.projection
}

func.func @test_eq_plus(%arg0: !proj.qubit) -> !proj.projection {
  // CHECK: %0 = proj.eq %arg0 : !proj.qubit, #proj.state<plus>
  %0 = proj.eq %arg0 : !proj.qubit, #proj.state<plus>
  func.return %0 : !proj.projection
}

// CHECK: proj.phase %angle
%angle = angle.zero
proj.phase %angle

// Test proj.qif with true region
func.func @test_if(%arg0: !proj.projection) {
  // CHECK: proj.qif %arg0 {
  // CHECK-NEXT:   ^bb0:
  // CHECK-NEXT:   }
  // CHECK-GENERIC: "proj.qif"(%[[ARG0:.*]]) ({
  // CHECK-GENERIC-NEXT:   ^bb0:
  // CHECK-GENERIC-NEXT:   }, {
  // CHECK-GENERIC-NEXT:   }) : (!proj.projection) -> ()
  proj.qif %arg0 {
  }
  func.return
}

// Test proj.qif with else region
func.func @test_if_else(%arg0: !proj.projection) {
  // CHECK: proj.qif %arg0 {
  // CHECK-NEXT:   ^bb0:
  // CHECK-NEXT:   } else {
  // CHECK-NEXT:   ^bb0:
  // CHECK-NEXT:   }
  // CHECK-GENERIC: "proj.qif"(%[[ARG0:.*]]) ({
  // CHECK-GENERIC-NEXT:   ^bb0:
  // CHECK-GENERIC-NEXT:   }, {
  // CHECK-GENERIC-NEXT:   ^bb0:
  // CHECK-GENERIC-NEXT:   }) : (!proj.projection) -> ()
  proj.qif %arg0 {
  } else {
  }
  func.return
}

// Test proj.alloc with different states
func.func @test_alloc() {
  // CHECK: %[[Q0:.*]] = proj.alloc<zero> : !proj.qubit
  // CHECK-GENERIC: %[[Q0:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<zero{{.*}}> : () -> !proj.qubit
  %q0 = proj.alloc <zero> : !proj.qubit
  // CHECK: %[[Q1:.*]] = proj.alloc<one> : !proj.qubit
  // CHECK-GENERIC: %[[Q1:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<one{{.*}}> : () -> !proj.qubit
  %q1 = proj.alloc <one> : !proj.qubit
  // CHECK: %[[QP:.*]] = proj.alloc<plus> : !proj.qubit
  // CHECK-GENERIC: %[[QP:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<plus{{.*}}> : () -> !proj.qubit
  %q_plus = proj.alloc <plus> : !proj.qubit
  // CHECK: %[[QM:.*]] = proj.alloc<minus> : !proj.qubit
  // CHECK-GENERIC: %[[QM:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<minus{{.*}}> : () -> !proj.qubit
  %q_minus = proj.alloc <minus> : !proj.qubit
  // CHECK: %[[QL:.*]] = proj.alloc<left> : !proj.qubit
  // CHECK-GENERIC: %[[QL:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<left{{.*}}> : () -> !proj.qubit
  %q_left = proj.alloc <left> : !proj.qubit
  // CHECK: %[[QR:.*]] = proj.alloc<right> : !proj.qubit
  // CHECK-GENERIC: %[[QR:.*]] = "proj.alloc"() <{{.*}}state = #proj.state<right{{.*}}> : () -> !proj.qubit
  %q_right = proj.alloc <right> : !proj.qubit
  func.return
}

// Test proj.measure
func.func @test_measure(%arg0: !proj.projection) -> i1 {
  // CHECK: %[[M0:.*]] = proj.measure %arg0
  // CHECK-GENERIC: %[[M0:.*]] = "proj.measure"(%[[ARG0:.*]]) : (!proj.projection) -> i1
  %m = proj.measure %arg0
  func.return %m : i1
}

// Test proj.pure function
// CHECK: proj.pure @pure_fn(%a: i1) {
// CHECK-NEXT:   proj.return
// CHECK-NEXT: }
// CHECK-GENERIC: "proj.pure"() <{{.*}}sym_name = "pure_fn"{{.*}}> ({
// CHECK-GENERIC-NEXT:   ^bb0(%[[A:.*]]: i1):
// CHECK-GENERIC-NEXT:     "proj.return"() : () -> ()
// CHECK-GENERIC-NEXT: }) : () -> ()
proj.pure @pure_fn(%a: i1) {
  proj.return
}

// Test proj.unitary function
// CHECK: proj.unitary @unitary_fn(%q: !proj.qubit) {
// CHECK-NEXT:   proj.return
// CHECK-NEXT: }
// CHECK-GENERIC: "proj.unitary"() <{{.*}}sym_name = "unitary_fn"{{.*}}> ({
// CHECK-GENERIC-NEXT:   ^bb0(%[[Q:.*]]: !proj.qubit):
// CHECK-GENERIC-NEXT:     "proj.return"() : () -> ()
// CHECK-GENERIC-NEXT: }) : () -> ()
proj.unitary @unitary_fn(%q: !proj.qubit) {
  proj.return
}

// Test proj.mixed function
// CHECK: proj.mixed @mixed_fn(%q: !proj.qubit) -> !proj.qubit {
// CHECK-NEXT:   proj.return %q : !proj.qubit
// CHECK-NEXT: }
// CHECK-GENERIC: "proj.mixed"() <{{.*}}sym_name = "mixed_fn"{{.*}}> ({
// CHECK-GENERIC-NEXT:   ^bb0(%[[Q:.*]]: !proj.qubit):
// CHECK-GENERIC-NEXT:     "proj.return"(%[[Q]]) : (!proj.qubit) -> ()
// CHECK-GENERIC-NEXT: }) : () -> ()
proj.mixed @mixed_fn(%q: !proj.qubit) -> !proj.qubit {
  proj.return %q : !proj.qubit
}

// Test proj.phase in unitary function
// CHECK: proj.unitary @phase_unitary() {
// CHECK-NEXT:   %[[ANGLE:.*]] = angle.zero
// CHECK-NEXT:   proj.phase %[[ANGLE]]
// CHECK-NEXT:   proj.return
// CHECK-NEXT: }
proj.unitary @phase_unitary() {
  %angle0 = angle.zero
  proj.phase %angle0
  proj.return
}

// Test proj.phase in mixed function
// CHECK: proj.mixed @phase_mixed() {
// CHECK-NEXT:   %[[ANGLE:.*]] = angle.zero
// CHECK-NEXT:   proj.phase %[[ANGLE]]
// CHECK-NEXT:   proj.return
// CHECK-NEXT: }
proj.mixed @phase_mixed() {
  %angle1 = angle.zero
  proj.phase %angle1
  proj.return
}

// Test proj.qif in unitary function
// CHECK: proj.unitary @if_unitary(%arg: !proj.projection) {
// CHECK-NEXT:   proj.qif %arg {
// CHECK-NEXT:   ^bb0:
// CHECK-NEXT:   }
// CHECK-NEXT:   proj.return
// CHECK-NEXT: }
proj.unitary @if_unitary(%arg: !proj.projection) {
  proj.qif %arg {
  }
  proj.return
}

// Test proj.qif in mixed function
// CHECK: proj.mixed @if_mixed(%arg: !proj.projection) {
// CHECK-NEXT:   proj.qif %arg {
// CHECK-NEXT:   ^bb0:
// CHECK-NEXT:   }
// CHECK-NEXT:   proj.return
// CHECK-NEXT: }
proj.mixed @if_mixed(%arg: !proj.projection) {
  proj.qif %arg {
  }
  proj.return
}

// Test proj.alloc in mixed function
// CHECK: proj.mixed @alloc_mixed() {
// CHECK-NEXT:   %[[Q:.*]] = proj.alloc<zero> : !proj.qubit
// CHECK-NEXT:   proj.return
// CHECK-NEXT: }
proj.mixed @alloc_mixed() {
  %q = proj.alloc <zero> : !proj.qubit
  proj.return
}

// Test proj.measure in mixed function
// CHECK: proj.mixed @measure_mixed(%arg: !proj.projection) -> i1 {
// CHECK-NEXT:   %[[M:.*]] = proj.measure %arg
// CHECK-NEXT:   proj.return %[[M]] : i1
// CHECK-NEXT: }
proj.mixed @measure_mixed(%arg: !proj.projection) -> i1 {
  %m = proj.measure %arg
  proj.return %m : i1
}

// Test proj.call operation with symbol table verification
// CHECK-LABEL: proj.pure @callee_fn
proj.pure @callee_fn(%a: i1) -> i1 {
  proj.return %a : i1
}

// CHECK-LABEL: proj.pure @caller_fn
// CHECK: %[[CALL:.*]] = proj.call @callee_fn(%arg0) : (i1) -> i1
// CHECK-NEXT: proj.return %[[CALL]] : i1
proj.pure @caller_fn(%arg0: i1) -> i1 {
  %call = proj.call @callee_fn(%arg0) : (i1) -> i1
  proj.return %call : i1
}
