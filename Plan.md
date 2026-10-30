# Type System Design for Projective Quantum Language

## Overview

This document specifies the type system for a quantum programming language based on projective predicates. The type system uses a borrowing-based approach to statically ensure that all projections commute, enabling safe composition of quantum predicates.

**Design constraint**: No higher-order functions. All functions are first-level definitions only.

## Core Types

```
qubit         - Qubit
proj          - Projection (opaque type)
bool          - Classical boolean (subtype of proj)
angle         - Classical angle (for Phase gates)
```

### Type Semantics

- **`qubit`**: a qubit value. **Function parameters of type `qubit` are considered borrowed** - they cannot be returned from the function.

- **`proj` (projection)**: a projection value that may borrow one or more qubits. Projections are first-class, copyable values (but cannot be passed to higher-order functions).

- **`bool` (boolean)**: Classical boolean value, used for measurement results and classical control flow. **`bool` is a subtype of `proj`** - booleans can be used wherever projections are expected (e.g., in `if` statements, with connectives). Can be freely returned from functions (no borrowing).

- **`angle` (angle)**: Classical angle value, used for Phase gate parameters. Can be freely returned from functions (no borrowing). Supports arithmetic operations and constants.

- **Qubit ownership**: Functions can return qubits, but **only qubits allocated within the function scope**. Function parameters (even `qubit`) cannot be returned.

## Surface Syntax

### Type Annotations

```rust
fn f(q: qubit, p: proj) -> proj { ... }         // qubit parameter
fn g(p: proj) -> proj { ... }                   // Projection parameter (always reborrowed)
```

**Notation**: All qubits use the simple `qubit` type without basis annotations.

### Expression Syntax

```rust
// Projection creation (both ASCII and Unicode notation accepted)
q == |0>         // Qubit q projected to |0> state
q == |0⟩         // Same as above (Unicode notation)
q == |+>         // Qubit q projected to |+> state
q == |L>         // Qubit q projected to |L> state

// Connectives (work on proj or bool, since bool <: proj)
p1 && p2         // Conjunction (and)
p1 || p2         // Disjunction (or)
p1 ^ p2          // Exclusive-or (xor)
!p               // Negation (not)
b1 && b2         // Boolean conjunction (bool <: proj)

// Conditional (accepts proj or bool, since bool <: proj)
if p {
    phase(PI)    // Phase gate (primitive operation)
}
if b {           // Boolean can be used directly
    phase(PI)
}

// Measurement
let b: bool = measure(p)    // Returns bool
if b {                      // bool can be used in if (subtype of proj)
    phase(PI)
}

// Allocation
let q = alloc |0>

// Angle arithmetic
let a1: angle = PI + PI/2;           // Addition
let a2: angle = PI - PI/4;           // Subtraction
let a3: angle = 2.0 * PI;            // Scalar multiplication
let a4: angle = PI / 3.0;            // Scalar division
let a5: angle = 0;                   // Zero constant
```

### Angle Constants

```rust
PI      // π (also accepts unicode: π)
0       // Zero angle
```

### Function Definitions

```rust
// Basic function
fn phase_oracle(q1: qubit, q2: qubit, p: proj) -> proj {
    if q1 == |0> && q2 == |1> && p {
        phase(PI)
    }
}

// Function with local variables
fn example(q: qubit) {
    let proj = q == |0>;
    if proj {
        phase(PI)
    }
}

// Function returning projection (only from reborrowed params)
fn identity(p: proj) -> proj {
    p
}
```

## Borrow Semantics

### Core Rules

1. **Projection Reborrowing**: Output projections reborrow from all input projection parameters. If a function takes `p: proj` and returns `proj`, the returned projection inherits all borrows from `p`.

2. **Local Qubit Borrows**: Functions can create projections on local qubits or `qubit` parameters, but these projections **cannot be returned**. Only projections that borrow from input `proj` parameters may escape.

3. **Borrow Release**: Borrows are released when the projection value goes out of scope (NLL-style semantics).

### Borrow Signature

Every function has an inferred borrow signature:

```
fn f(q: qubit, p: proj) -> proj
```

**Semantics**:
- `q: qubit` - Caller must provide qubit
- `p: proj` - Projection parameter (always reborrowed)
- Return `proj` - Reborrow from input `p` plus any new borrows created in function body

**Inference Rules**:
- Walk function body to determine which qubits are borrowed
- Returned projections can only borrow from input `proj` parameters

## Validation Rules

### Function Body Validation

1. **Qubit parameter usage**: If `q: qubit`, projections can be created on `q`, but cannot be returned

2. **Projection reborrowing**: Returned projections must only borrow from input `proj` parameters (not from local qubits or `qubit` params)

3. **Qubit return validation**: Functions can return `qubit`, but **only qubits allocated within the function scope**. Function parameters of type `qubit` cannot be returned.

4. **Classical return validation**: Functions can freely return `bool` and `angle` (classical types have no borrowing semantics).

### Call-Site Validation

1. **Projection availability**: Actual projection arguments must not be currently borrowed

## Examples

### Valid Programs

```rust
// Example 1: Basic function
fn phase_oracle(q1: qubit, q2: qubit, p: proj) -> proj {
    if q1 == |0> && q2 == |1> && p {
        phase(PI)
    }
}

// Call site
let q1 = alloc |0>;
let q2 = alloc |0>;
let p = q1 == |0>;
phase_oracle(q1, q2, p);  // ✅ OK
```

```rust
// Example 2: Projection reborrowing
fn identity(p: proj) -> proj {
    p  // ✅ OK - only reborrow from input proj
}

fn extend(q: qubit, p: proj) -> proj {
    p && (q == |0>  // ✅ OK - reborrow p + new borrow on q
}
```

```rust
// Example 3: Qubit parameter (not returned)
fn use_local(q: qubit) {
    let proj = q == |0>;
    if proj {
        phase(PI)
    }
    // proj released at end of scope
}
```

```rust
// Example 4: Multiple borrows
fn multi_borrow(q1: qubit, q2: qubit) {
    let p1 = q1 == |0>;
    let p2 = q2 == |1>;
    if p1 && p2 {
        phase(PI)
    }
}
```

```rust
// Example 5: Returning locally-allocated qubit
fn make_qubit() -> qubit {
    let q = alloc |0>;
    q  // ✅ OK - q was allocated in this function
}
```

```rust
// Example 6: Using returned qubit
fn use_returned() {
    let q = make_qubit();
    let proj = q == |0>;
    if proj {
        phase(PI)
    }
}
```

```rust
// Example 7: Returning classical data
fn measure_qubit(q: qubit) -> bool {
    let proj = q == |0>;
    measure(proj)  // ✅ OK - bool can be freely returned
}
```

```rust
// Example 8: Returning angle
fn get_phase() -> angle {
    PI  // ✅ OK - angle can be freely returned
}
```

```rust
// Example 9: Angle arithmetic
fn custom_phase(q: qubit, theta: angle) {
    let adjusted = theta + PI/2;
    phase(adjusted)  // ✅ OK - angle addition
}

fn half_phase(q: qubit) {
    phase(PI / 2.0)  // ✅ OK - angle division
}

fn double_phase(q: qubit) {
    phase(2.0 * PI)  // ✅ OK - scalar multiplication
}
```

```rust
// Example 10: Boolean as projection (bool <: proj)
fn use_measurement(q: qubit) {
    let b: bool = measure(q == |0>);
    if b {              // ✅ OK - bool can be used in if (subtype of proj)
        phase(PI)
    }
}

fn boolean_ops(q1: qubit, q2: qubit) {
    let b1: bool = measure(q1 == |0>);
    let b2: bool = measure(q2 == |0>);
    if b1 && b2 {       // ✅ OK - boolean conjunction
        phase(PI)
    }
}
```

### Invalid Programs

```rust
// Example 1: Returning local qubit borrow
fn make_proj(q: qubit) -> proj {
    q == |0>  // ❌ ERROR - cannot return projection borrowing local q
}
```

```rust
// Example 2: Returning parameter qubit
fn return_param(q: qubit) -> qubit {
    q  // ❌ ERROR - cannot return qubit parameter
}
```

```rust
// Example 3: Cannot return borrowed qubit
fn return_borrowed(q1: qubit, q2: qubit) -> qubit {
    let q3 = alloc |0>;
    q1  // ❌ ERROR - q1 is a parameter, cannot return
}
```

## Borrow Analysis Algorithm

The borrow checker is a forward dataflow analysis that runs after liveness analysis. It tracks which qubits are borrowed, in which bases, and by which projections.

### Borrow State

For each qubit, the analysis maintains a borrow state:

```
BorrowState:
  projections: set[SSAValue]  // live projections borrowing this qubit
```

- **Empty set**: qubit is not borrowed
- **Non-empty set**: qubit is borrowed by the listed projections

### Analysis State

The analysis state at each program point is a mapping:

```
AnalysisState = dict[SSAValue, BorrowState]  // qubit SSA → borrow state
```

### Forward Dataflow

The analysis processes operations in forward order through each block:

1. **Projection creation** (`q == |0>`, `q == |+>`, `q == |L>`):
   - Add the projection to the qubit's borrow set

2. **Compound projections** (`p1 && p2`, `!p`, `p1 ^ p2`, `p1 || p2`):
   - Result projection inherits borrows from all operand projections
   - For each qubit borrowed by any operand, add result to that qubit's borrow set

3. **Projection use** (e.g., `if p`):
   - No change to borrow state (projections are copyable)

4. **Projection release** (when projection goes dead):
   - Use liveness info to detect when projection is no longer live
   - Remove projection from all qubits it borrows
   - If no projections remain for a qubit, reset to empty set

### Integration with Liveness

The borrow checker takes `LivenessInfo` as input and uses it to detect when projections are released:

```
for op in forward_order(block):
    live_after = liveness.get_live_after(op)
    
    # Remove projections that are no longer live
    for proj in current_projections - live_after:
        release_borrows(proj)
    
    # Process operation's effect on borrows
    if is_projection_create(op):
        add_borrow(op.result, op.qubit, op.basis)
```

### Function Borrow Signature

The borrow signature is inferred from the analysis:

**Assumptions**:
- Returned projections inherit borrows from input projection parameters
- Returned projections **cannot** borrow locally allocated qubits

**Qubit Tracking**:
The analysis tracks which qubits are:
- **Parameters**: Cannot be borrowed by returned projections
- **Locally allocated**: Cannot be borrowed by returned projections

**Inference**:
1. Run forward borrow analysis on function body
2. Track which qubits are parameters vs. locally allocated (by definition point)
3. At function exit, validate:
   - All locally allocated qubits have no active borrows
   - This ensures returned projections don't borrow local qubits
4. Signature includes borrows from:
   - Input projection parameters (inherited by returned projections)

### Call-Site Validation

At each call site:

1. **Check projection availability**: actual projection args must not be currently borrowed



## Syntax Summary

| Concept | Syntax | Example |
|---------|--------|---------|
| Qubit type | `qubit` | `q: qubit` |
| Projection type | `proj` | `p: proj` |
| Boolean type | `bool` | `b: bool` |
| Angle type | `angle` | `theta: angle` |
| Projection | `q == \|bool>` | `q == \|0>` or `q == \|0⟩` |
| Conjunction | `p1 && p2` | `p1 && p2` |
| Disjunction | `p1 \|\| p2` | `p1 \|\| p2` |
| XOR | `p1 ^ p2` | `p1 ^ p2` |
| Negation | `!p` | `!p` |
| Conditional | `if x { ... }` | `if p { phase(PI) }` or `if b { phase(PI) }` |
| Measurement | `measure(p)` | `let b: bool = measure(p)` |
| Allocation | `alloc \|bool>` | `let q = alloc \|0>` |
| Phase gate | `phase(theta)` | `phase(PI)` |
| Angle addition | `a1 + a2` | `PI + PI/2` |
| Angle subtraction | `a1 - a2` | `PI - PI/4` |
| Scalar mult | `c * a` | `2.0 * PI` |
| Scalar div | `a / c` | `PI / 3.0` |
| Angle constants | `PI`, `π`, `0` | `phase(PI)` |
| Function | `fn name(params) -> ret { ... }` | `fn f(q: qubit) { ... }` |

**Note**: State notation accepts both ASCII (`|0>`) and Unicode (`|0⟩`) syntax. Angle constant `PI` also accepts Unicode `π`.

**Subtyping**: `bool <: proj` - booleans are a subtype of projections. This means:
- Booleans can be used in `if` statements
- Boolean connectives (`&&`, `||`, `^`, `!`) work on both `bool` and `proj`
- Measurement results (`bool`) can be used directly in quantum conditionals

## References

- Quantum logic and projection lattices
- Rust borrow checker and lifetime elision
- MLIR dialect design patterns
- Linear and affine type systems
