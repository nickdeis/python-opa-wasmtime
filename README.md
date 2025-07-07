# Open Policy Agent WebAssembly SDK for Python

This is based off [opa-wasm](https://pypi.org/project/opa-wasm/), which uses wasmer, but this targets wasmtime. This allows you to use OPA WASM binaries in Python versions above 3.10, which is the cutoff for wasmer.

# Getting Started

## Install the module

```
pip install opa-wasmtime
```

## Usage

There are only a couple of steps required to start evaluating the policy.

```python
# Import the module
from opa_wasmtime import OPAPolicy

# Load a policy by specifying its file path
policy = OPAPolicy('./policy.wasm')

# Optional: Set policy data
policy.set_data({"company_name": "ACME"})

# Evaluate the policy
input = {"user": "alice"}
result = policy.evaluate(input)
```

## Support Targets

This module has been tested on python 3.10 and above and wasmtime 27.0.2 and above.

## Writing the policy

See [https://www.openpolicyagent.org/docs/latest/how-do-i-write-policies/](https://www.openpolicyagent.org/docs/latest/how-do-i-write-policies/)

## Compiling the policy

Either use the [Compile REST API](https://www.openpolicyagent.org/docs/latest/rest-api/#compile-api) or `opa build` CLI tool.

For example, with OPA v0.20.5+:

```bash
opa build -t wasm -e 'example/allow' example.rego
```

Which compiles the `example.rego` policy file with the result set to
`data.example.allow`. The result will be an OPA bundle with the `policy.wasm`
binary included.

See `opa build --help` for more details.

## Credits

This project was inspired by the equivalent NPM Module [@open-policy-agent/opa-wasm](https://github.com/open-policy-agent/npm-opa-wasm)
