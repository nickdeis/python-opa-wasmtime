import itertools
from itertools import repeat
import json
from pathlib import Path
from typing import Union, Tuple

from wasmtime import (
    FuncType,
    Store,
    Module,
    Instance,
    Func,
    Memory,
    MemoryType,
    Linker,
    Limits,
    ValType,
    Global,
)


import time


def benchmark(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Benchmark: {func.__name__} took {end_time - start_time:.6f} seconds")
        return result

    return wrapper


i32 = ValType.i32()


class OPAPolicy:
    store: Store
    memory: Memory
    linker: Linker
    module: Module
    instance: Instance
    supports_fastpath: bool

    def __init__(self, wasm_path, min_memory=2024, max_memory=5120, builtins=None):
        if not Path(wasm_path).is_file():
            raise ValueError(f"Path: {wasm_path} is not a valid file")

        self.store = Store()
        self.memory = Memory(
            self.store,
            MemoryType(limits=Limits(min=min_memory, max=max_memory), shared=False),
        )

        self.linker = Linker(self.store.engine)
        self.linker.define(
            store=self.store, module="env", name="memory", item=self.memory
        )
        self.linker.define(
            store=self.store,
            module="env",
            name="opa_builtin0",
            item=Func(
                self.store,
                FuncType([i32, i32], [i32]),
                self._opa_builtin0,
            ),
        )
        self.linker.define(
            store=self.store,
            module="env",
            name="opa_builtin1",
            item=Func(
                self.store,
                FuncType(list(repeat(i32, 3)), [i32]),
                self._opa_builtin1,
            ),
        )
        self.linker.define(
            store=self.store,
            module="env",
            name="opa_builtin2",
            item=Func(
                self.store,
                FuncType(list(repeat(i32, 4)), [i32]),
                self._opa_builtin2,
            ),
        )
        self.linker.define(
            store=self.store,
            module="env",
            name="opa_builtin3",
            item=Func(
                self.store,
                FuncType(list(repeat(i32, 5)), [i32]),
                self._opa_builtin3,
            ),
        )
        self.linker.define(
            store=self.store,
            module="env",
            name="opa_builtin4",
            item=Func(
                self.store,
                FuncType(list(repeat(i32, 6)), [i32]),
                self._opa_builtin4,
            ),
        )
        self.linker.define(
            store=self.store,
            module="env",
            name="opa_abort",
            item=Func(self.store, FuncType([i32], []), self._opa_abort),
        )
        self.linker.define(
            store=self.store,
            module="env",
            name="opa_println",
            item=Func(self.store, FuncType([i32], []), self._opa_println),
        )

        self.module = Module.from_file(self.store.engine, wasm_path)
        self.instance = self.linker.instantiate(module=self.module, store=self.store)
        self.exports = self.instance.exports(self.store)
        abi_major_version = self.get_export("opa_wasm_abi_version")
        if abi_major_version and abi_major_version != 1:
            raise RuntimeError(f"Unsupported ABI Version {abi_major_version}")

        abi_minor_version = self.get_export("opa_wasm_abi_minor_version")
        self.supports_fastpath = abi_minor_version >= 2

        if not self.supports_fastpath:
            raise RuntimeError(f"ABI Version must be greater than or equal to 2")

        self.entrypoints = self._fetch_json(self.get_export("entrypoints")())

        self.builtins_by_id = self._create_builtins_map(builtins if builtins else {})

        # Set the default value for data. This can be overwritten by set_data
        self.data_address = self._put_json({})

        self.base_heap_pointer = self.get_export("opa_heap_ptr_get")()
        self.data_heap_pointer = self.base_heap_pointer
        self.heap_pointer = self.base_heap_pointer
        self.opa_eval = self.get_export("opa_eval")

    def get_export(self, name: str):
        export = self.exports[name]
        if isinstance(export, Global):
            return export.value(self.store)
        if isinstance(export, Func):

            def wrap(*args):
                return export(self.store, *args)

            return wrap
        return export

    def evaluate(self, input, entrypoint=0):
        entrypoint = self._lookup_entrypoint(entrypoint)

        # Before each evaluation, reset the heap pointer to the data_heap_pointer
        self.heap_pointer = self.data_heap_pointer
        return self._evaluate_fastpath(input, entrypoint)

    def set_data(self, data):
        # Reset the heap to the base_heap_pointer when data is changed
        self.get_export("opa_heap_ptr_set")(self.base_heap_pointer)

        # Perform update of data and pointers
        self.data_address = self._put_json(data)
        self.data_heap_pointer = self.get_export("opa_heap_ptr_get")()
        self.heap_pointer = self.data_heap_pointer

    def _evaluate_fastpath(self, input, entrypoint):
        input_address, input_length = self._put_json_in_memory(input)
        result = self.opa_eval(
            0,
            entrypoint,
            self.data_address,
            input_address,
            input_length,
            self.heap_pointer,
            0,
        )
        return self._fetch_json_raw(result)

    def _fetch_json(self, address: int):
        json_address = self.get_export("opa_json_dump")(address)
        return self._fetch_json_raw(json_address)

    def _fetch_json_raw(self, json_address: int):
        bina = self._fetch_string_as_bytearray(json_address)
        return json.loads(bina)

    def _put_json(self, value: dict) -> int:
        """
        This method puts a json into opa memory
        """
        json_string = json.dumps(value).encode("utf-8")
        size = len(json_string)

        dest_string_address = self.get_export("opa_malloc")(size)
        self.memory.write(self.store, bytearray(json_string), dest_string_address)

        dest_json_address = self.get_export("opa_json_parse")(dest_string_address, size)

        if dest_json_address == 0:
            raise RuntimeError("Failed to parse JSON Value")

        return dest_json_address

    def _put_json_in_memory(self, value) -> tuple[int, int]:
        json_string = json.dumps(value).encode("utf-8")
        input_length = len(json_string)

        input_address = self.heap_pointer
        self.memory.write(self.store, bytearray(json_string), input_address)
        self.heap_pointer = input_address + input_length
        return input_address, input_length

    def _fetch_string_as_bytearray(self, address) -> bytearray:
        memory_size = self.memory.data_len(self.store)
        memory_buffer = self.memory.read(self.store, start=address, stop=memory_size)
        json_string_iterator = itertools.takewhile(
            bool, memory_buffer
        )  # Null terminated string
        return bytearray(json_string_iterator)

    def _dispatch(self, id: int, *args):
        return self._put_json(self.builtins_by_id[id](*args))

    def _create_builtins_map(self, builtins):
        builtins_by_id = {}
        builtin_functions_required = self._fetch_json(self.get_export("builtins")())

        for function_name, id in builtin_functions_required.items():
            if function_name not in builtins:
                raise LookupError(
                    f"A required builtin '{function_name}' function was not provided."
                )

            builtins_by_id[id] = builtins[function_name]

        return builtins_by_id

    def _opa_builtin0(self, builtin_id: int, ctx: int) -> int:
        return self._dispatch(builtin_id)

    def _opa_builtin1(self, builtin_id: int, ctx: int, _1: int) -> int:
        return self._dispatch(builtin_id, *self._make_args_for_builtin(_1))

    def _opa_builtin2(self, builtin_id: int, ctx: int, _1: int, _2: int) -> int:
        return self._dispatch(builtin_id, *self._make_args_for_builtin(_1, _2))

    def _opa_builtin3(
        self, builtin_id: int, ctx: int, _1: int, _2: int, _3: int
    ) -> int:
        return self._dispatch(builtin_id, *self._make_args_for_builtin(_1, _2, _3))

    def _opa_builtin4(
        self, builtin_id: int, ctx: int, _1: int, _2: int, _3: int, _4: int
    ) -> int:
        return self._dispatch(builtin_id, *self._make_args_for_builtin(_1, _2, _3, _4))

    def _opa_abort(self, address: int):
        raise RuntimeError(
            f"OPA Aborted with message: {self._fetch_string_as_bytearray(address).decode('utf-8')}"
        )

    def _opa_println(self, address: int):
        print(self._fetch_string_as_bytearray(address).decode("utf-8"))

    def _make_args_for_builtin(self, *addresses):
        return [self._fetch_json(address) for address in addresses]

    def _lookup_entrypoint(self, entrypoint: Union[str, int]) -> int:
        if isinstance(entrypoint, int) and entrypoint < len(self.entrypoints):
            return entrypoint

        if isinstance(entrypoint, str) and entrypoint in self.entrypoints:
            return self.entrypoints[entrypoint]

        raise ValueError(f"The specified entrypoint '{entrypoint}' is not valid")
