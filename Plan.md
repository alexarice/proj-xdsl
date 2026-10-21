# Type System Design for Projective Quantum Language

## Overview

This document specifies the type system for a quantum programming language based on projective predicates. The type system uses a borrowing-based approach to statically ensure that all projections commute, enabling safe composition of quantum predicates.

**Design constraint**: No higher-order functions. All functions are first-level definitions only.

## Core Types

```
Q           - Qubit
Q<B>        - Qubit borrowed in basis B, where B ∈ {X, Y, Z}
P           - Projection (opaque type)
B           - Classical boolean (subtype of P)
A           - Classical angle (for Phase gates)
```

### Type Semantics

- **`Q` (unborrowed qubit)**: A qubit that is not currently borrowed. Can be used to create projections in any basis, but projections borrowing this qubit cannot escape the scope. **Function parameters of type `Q` are considered borrowed** - they cannot be returned from the function.

- **`Q<B>` (borrowed qubit)**: A qubit that is borrowed in a specific basis. Only projections in that basis (or compatible bases) can be created.

- **`P` (projection)**: A projection value that may borrow one or more qubits. Projections are first-class, copyable values (but cannot be passed to higher-order functions).

- **`B` (boolean)**: Classical boolean value, used for measurement results and classical control flow. **`B` is a subtype of `P`** - booleans can be used wherever projections are expected (e.g., in `if` statements, with connectives). Can be freely returned from functions (no borrowing).

- **`A` (angle)**: Classical angle value, used for Phase gate parameters. Can be freely returned from functions (no borrowing). Supports arithmetic operations and constants.

- **Basis compatibility**:
  - Same basis: Compatible (multiple Z-borrows allowed)
  - Different basis: Incompatible (X and Z on same qubit = error)
  - Total borrow: Control flow disagreement creates a "total borrow" that prevents any new borrows

- **Qubit ownership**: Functions can return qubits, but **only qubits allocated within the function scope**. Function parameters (even `Q`) cannot be returned.

## Surface Syntax

### Type Annotations

```rust
fn f(q: Q<Z>, p: P) -> P { ... }      // Q borrowed in Z basis
fn g(q: Q, p: P) -> P { ... }         // Q unborrowed
fn h(p: P) -> P { ... }               // Projection parameter (always reborrowed)
```

**Notation**: `Q<B>` uses angle bracket syntax for basis annotations. Only one basis annotation is allowed per qubit parameter.

### Expression Syntax

```rust
// Projection creation (both ASCII and Unicode notation accepted)
q == |0>         // Qubit q projected to |0> state (Z basis)
q == |0⟩         // Same as above (Unicode notation)
q == |+>         // Qubit q projected to |+> state (X basis)
q == |L>         // Qubit q projected to |L> state (Y basis)

// Connectives (work on P or B, since B <: P)
p1 && p2         // Conjunction (and)
p1 || p2         // Disjunction (or)
p1 ^ p2          // Exclusive-or (xor)
!p               // Negation (not)
b1 && b2         // Boolean conjunction (B <: P)

// Conditional (accepts P or B, since B <: P)
if p {
    phase(PI)    // Phase gate (primitive operation)
}
if b {           // Boolean can be used directly
    phase(PI)
}

// Measurement
let b: B = measure(p)    // Returns B
if b {                   // B can be used in if (subtype of P)
    phase(PI)
}

// Allocation
let q = alloc |0>

// Angle arithmetic
let a1: A = PI + PI/2;           // Addition
let a2: A = PI - PI/4;           // Subtraction
let a3: A = 2.0 * PI;            // Scalar multiplication
let a4: A = PI / 3.0;            // Scalar division
let a5: A = 0;                   // Zero constant
```

### Angle Constants

```rust
PI      // π (also accepts unicode: π)
0       // Zero angle
```

### Function Definitions

```rust
// Basic function
fn phase_oracle(q1: Q<Z>, q2: Q<Z>, p: P) -> P {
    if q1 == |0> && q2 == |1> && p {
        phase(PI)
    }
}

// Function with local variables
fn example(q: Q) {
    let proj = q == |0>;
    if proj {
        phase(PI)
    }
}

// Function returning projection (only from reborrowed params)
fn identity(p: P) -> P {
    p
}
```

## Borrow Semantics

### Core Rules

1. **Projection Reborrowing**: Output projections reborrow from all input projection parameters. If a function takes `p: P` and returns `P`, the returned projection inherits all borrows from `p`.

2. **Local Qubit Borrows**: Functions can create projections on local qubits or bare `Q` parameters, but these projections **cannot be returned**. Only projections that borrow from input `P` parameters may escape.

3. **Basis Compatibility**: At any program point, a qubit cannot be borrowed in incompatible bases simultaneously. Same-basis borrows are compatible.

4. **Total Borrow**: When control flow paths disagree on which basis a qubit is borrowed in, the qubit receives a "total borrow" that prevents any new borrows until the projection is released.

5. **Borrow Release**: Borrows are released when the projection value goes out of scope (NLL-style semantics).

### Borrow Signature

Every function has an inferred borrow signature:

```
fn f(q: Q<Z>, p: P) -> P
```

**Semantics**:
- `q: Q<Z>` - Caller must provide qubit available in Z basis
- `p: P` - Projection parameter (always reborrowed)
- Return `P` - Reborrow from input `p` plus any new borrows created in function body

**Inference Rules**:
- Walk function body to determine which qubits are borrowed and in which bases
- For control flow: union of bases from all paths
- Multiple bases for same qubit → total borrow
- Returned projections can only borrow from input `P` parameters

## Validation Rules

### Function Body Validation

1. **Qubit parameter usage**: If `q: Q<B>`, all projections on `q` must be in basis `B` (or compatible)

2. **Bare qubit usage**: If `q: Q`, projections can be created in any basis, but cannot be returned

3. **Projection reborrowing**: Returned projections must only borrow from input `P` parameters (not from local qubits or bare `Q` params)

4. **Qubit return validation**: Functions can return `Q`, but **only qubits allocated within the function scope**. Function parameters of type `Q` cannot be returned.

5. **Classical return validation**: Functions can freely return `B` and `A` (classical types have no borrowing semantics).

6. **Borrow compatibility**: No qubit can have incompatible active borrows at any program point

### Call-Site Validation

1. **Qubit availability**: Actual qubit arguments must be available in the required basis

2. **Projection availability**: Actual projection arguments must not be currently borrowed

3. **Borrow conflict detection**: If caller has incompatible borrows active, call is invalid

## Examples

### Valid Programs

```rust
// Example 1: Compatible borrows
fn phase_oracle(q1: Q<Z>, q2: Q<Z>, p: P) -> P {
    if q1 == |0> && q2 == |1> && p {
        phase(PI)
    }
}

// Call site (valid - all Z basis)
let q1 = alloc |0>;
let q2 = alloc |0>;
let p = q1 == |0>;
phase_oracle(q1, q2, p);  // ✅ OK
```

```rust
// Example 2: Projection reborrowing
fn identity(p: P) -> P {
    p  // ✅ OK - only reborrow from input P
}

fn extend(q: Q<Z>, p: P) -> P {
    p && (q == |0>  // ✅ OK - reborrow p + new Z borrow on q
}
```

```rust
// Example 3: Bare qubit (not returned)
fn use_local(q: Q) {
    let proj = q == |0>;  // ✅ OK - Z basis projection
    if proj {
        phase(PI)
    }
    // proj released at end of scope
}
```

```rust
// Example 4: Multiple compatible borrows
fn multi_borrow(q1: Q<Z>, q2: Q<Z>) {
    let p1 = q1 == |0>;  // Z borrow on q1
    let p2 = q2 == |1>;  // Z borrow on q2
    if p1 && p2 {
        phase(PI)
    }
}
```

```rust
// Example 5: Returning locally-allocated qubit
fn make_qubit() -> Q {
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
fn measure_qubit(q: Q) -> B {
    let proj = q == |0>;
    measure(proj)  // ✅ OK - B can be freely returned
}
```

```rust
// Example 8: Returning angle
fn get_phase() -> A {
    PI  // ✅ OK - A can be freely returned
}
```

```rust
// Example 9: Angle arithmetic
fn custom_phase(q: Q, theta: A) {
    let adjusted = theta + PI/2;
    phase(adjusted)  // ✅ OK - angle addition
}

fn half_phase(q: Q) {
    phase(PI / 2.0)  // ✅ OK - angle division
}

fn double_phase(q: Q) {
    phase(2.0 * PI)  // ✅ OK - scalar multiplication
}
```

```rust
// Example 10: Boolean as projection (B <: P)
fn use_measurement(q: Q) {
    let b: B = measure(q == |0>);
    if b {              // ✅ OK - B can be used in if (subtype of P)
        phase(PI)
    }
}

fn boolean_ops(q1: Q, q2: Q) {
    let b1: B = measure(q1 == |0>);
    let b2: B = measure(q2 == |0>);
    if b1 && b2 {       // ✅ OK - boolean conjunction
        phase(PI)
    }
}
```

### Invalid Programs

```rust
// Example 1: Incompatible bases
fn bad(q: Q<Z>, p: P) -> P {
    if q == |+> && p {  // ❌ ERROR - q is Q<Z> but X basis used
        phase(PI)
    }
}
```

```rust
// Example 2: Returning local qubit borrow
fn make_proj(q: Q) -> P {
    q == |0>  // ❌ ERROR - cannot return projection borrowing local q
}
```

```rust
// Example 3: Call-site conflict
fn f(q: Q<Z>, p: P) -> P { ... }

let q = alloc |0>;
let p1 = q == |0>;      // q borrowed in Z
let p2 = q == |+>;      // ❌ ERROR - q already borrowed in Z, can't borrow in X
f(q, p1);
```

```rust
// Example 4: Total borrow from control flow
fn conditional(c: B, q: Q) -> P {
    if c {
        q == |0>    // Z basis
    } else {
        q == |+>    // X basis
    }
    // ❌ ERROR - total borrow on q (Z or X), caller cannot use q
}
```

```rust
// Example 5: Incompatible borrows on same qubit
fn incompatible(q: Q<Z>, p: P) -> P {
    let p2 = q == |+>;  // ❌ ERROR - q is Q<Z>, can't borrow in X
    p && p2
}
```

```rust
// Example 8: Returning parameter qubit
fn return_param(q: Q) -> Q {
    q  // ❌ ERROR - cannot return qubit parameter (even if bare Q)
}
```

```rust
// Example 9: Cannot return borrowed qubit
fn return_borrowed(q1: Q, q2: Q) -> Q {
    let q3 = alloc |0>;
    q1  // ❌ ERROR - q1 is a parameter, cannot return
}
```

## Borrow Analysis Algorithm

### Phase 1: Signature Inference

For each function:
1. Walk function body
2. Track active borrows per qubit (SSA value → set of bases)
3. At control flow merge points: union of bases from all paths
4. Multiple bases for same qubit → mark as total borrow
5. Determine which borrows escape in return value

### Phase 2: Body Validation

For each function:
1. Verify qubit parameter usage matches signature
2. Verify returned projections only borrow from input `P` parameters
3. Verify returned qubits are locally allocated (not parameters)
4. Verify no incompatible borrows at any program point
5. Verify total borrows don't have new borrows created

### Phase 3: Call-Site Validation

For each call:
1. Check actual qubit params have required basis availability
2. Check actual projection params are not currently borrowed
3. Check no conflicts between new borrows and existing borrows

## Open Questions

1. **Unitary marking**: How to mark functions/blocks as unitary, ensuring they don't contain measurements? This would prevent measurement results from being used in quantum `if` statements, maintaining a clear separation between:
   - **Unitary code**: Only quantum projections, no measurements
   - **Measurement code**: Can measure, but restricted in quantum conditionals

   Possible approaches:
   - Effect system (track `measure` effect)
   - Separate function types (`fn` vs `unitary fn`)
   - Region attributes in IR



## Syntax Summary

| Concept | Syntax | Example |
|---------|--------|---------|
| Qubit type | `Q` or `Q<B>` | `q: Q<Z>` |
| Projection type | `P` | `p: P` |
| Boolean type | `B` | `b: B` |
| Angle type | `A` | `theta: A` |
| Projection | `q == \|B>` | `q == \|0>` or `q == \|0⟩` |
| Conjunction | `p1 && p2` | `p1 && p2` |
| Disjunction | `p1 \|\| p2` | `p1 \|\| p2` |
| XOR | `p1 ^ p2` | `p1 ^ p2` |
| Negation | `!p` | `!p` |
| Conditional | `if x { ... }` | `if p { phase(PI) }` or `if b { phase(PI) }` |
| Measurement | `measure(p)` | `let b: B = measure(p)` |
| Allocation | `alloc \|B>` | `let q = alloc \|0>` |
| Phase gate | `phase(theta)` | `phase(PI)` |
| Angle addition | `a1 + a2` | `PI + PI/2` |
| Angle subtraction | `a1 - a2` | `PI - PI/4` |
| Scalar mult | `c * a` | `2.0 * PI` |
| Scalar div | `a / c` | `PI / 3.0` |
| Angle constants | `PI`, `π`, `0` | `phase(PI)` |
| Function | `fn name(params) -> ret { ... }` | `fn f(q: Q) { ... }` |

**Note**: State notation accepts both ASCII (`|0>`) and Unicode (`|0⟩`) syntax. Angle constant `PI` also accepts Unicode `π`.

**Subtyping**: `B <: P` - booleans are a subtype of projections. This means:
- Booleans can be used in `if` statements
- Boolean connectives (`&&`, `||`, `^`, `!`) work on both `B` and `P`
- Measurement results (`B`) can be used directly in quantum conditionals

## References

- Quantum logic and projection lattices
- Rust borrow checker and lifetime elision
- MLIR dialect design patterns
- Linear and affine type systems
