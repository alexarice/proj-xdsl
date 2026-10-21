// RUN: XDSL_ROUNDTRIP

// Test BasisAttr and StateAttr
"test.op"() {
  // CHECK: basis_x = #proj.basis<x>
  basis_x = #proj.basis<x>,
  // CHECK-SAME: basis_y = #proj.basis<y>
  basis_y = #proj.basis<y>,
  // CHECK-SAME: basis_z = #proj.basis<z>
  basis_z = #proj.basis<z>,
  // CHECK-SAME: state_zero = #proj.state<zero>
  state_zero = #proj.state<zero>,
  // CHECK-SAME: state_one = #proj.state<one>
  state_one = #proj.state<one>,
  // CHECK-SAME: state_plus = #proj.state<plus>
  state_plus = #proj.state<plus>,
  // CHECK-SAME: state_minus = #proj.state<minus>
  state_minus = #proj.state<minus>,
  // CHECK-SAME: state_left = #proj.state<left>
  state_left = #proj.state<left>,
  // CHECK-SAME: state_right = #proj.state<right>
  state_right = #proj.state<right>
} : () -> ()
