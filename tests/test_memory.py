from opa_wasmtime import OPAPolicy


def test_memory_corruption_type_2():
    # Regression test
    policy = OPAPolicy("./policy_memory_check.wasm")
    policy.set_data({})
    input = {"roles": ["AAAAAAAAAAAAAAA#BBBBB#CCCCC" for _ in range(135)]}
    assert policy.evaluate(input) == [
        {"result": {"allow": True, "unique_roles": ["AAAAAAAAAAAAAAA#BBBBB#CCCCC"]}}
    ]


def test_memory_corruption_type_1():
    # Regression test
    policy = OPAPolicy("./policy_memory_check.wasm")
    policy.set_data({})
    input = {"roles": ["AAAAAAAAAAAAAAA#BBBBB#CCCCC" for _ in range(122)]}
    assert policy.evaluate(input) == [
        {"result": {"allow": True, "unique_roles": ["AAAAAAAAAAAAAAA#BBBBB#CCCCC"]}}
    ]


def test_memory_leak():
    # Regression test - fastpath memory leak
    policy = OPAPolicy("./policy_memory_check.wasm")
    policy.set_data({})
    input = {"roles": ["AAAAAAAAAAAAAAA#BBBBB#CCCCC" for _ in range(5)]}

    for _ in range(1000):
        assert policy.evaluate(input) == [
            {"result": {"allow": True, "unique_roles": ["AAAAAAAAAAAAAAA#BBBBB#CCCCC"]}}
        ]
