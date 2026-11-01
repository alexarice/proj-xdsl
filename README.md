# proj-xdsl

A quantum programming language based on projective predicates, built on the xDSL framework.

## Installation

### Prerequisites
- Python 3.11+
- `uv` package manager (recommended) or `pip`

### Set up virtual environment
```bash
git clone https://github.com/xdslproject/proj-xdsl.git
cd proj-xdsl
make venv
```

### Activate the environment
```bash
source .venv/bin/activate
```

## Quick Start

### Example Program

```proj
// Define a pure function (no side effects)
pure fn angle_avg(a1: angle, a2: angle) -> angle {
    0.5 * (a1 + a2)
}

// Unitary function (reversible operations)
unitary fn Z(q: qubit) {
    if q == |0> {
        ph(pi)
    }
}

// Mixed function (can allocate and measure)
mixed fn bell_pair() {
    let q1 = alloc |+>;
    let q2 = alloc |0>;
    if q1 == |0> && q2 == |-> {
      ph(pi)
    }
}
```

### Running Programs

First activate the virtual environment:
```bash
source .venv/bin/activate
```

Then run commands:
```bash
# Parse and check a program
xdsl-opt program.proj
```

## Development

Test can be run with:
```bash
make tests
```

All commits should be formatted with the precommit hook. This can be run with:
```bash
make precommit
```
or the hook can be installed with:
```bash
make precommit-install
```

## License

This project is licensed under the [MIT License](LICENSE).
