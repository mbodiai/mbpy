from pathlib import Path
import re
import traceback
from types import FunctionType
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Generic, List, Optional, Self, Tuple, Type, TypeAlias, TypeVar, Union, dataclass_transform, NamedTuple, get_args
from collections import defaultdict, namedtuple
from fastapi.datastructures import Default
from typing_extensions import TypeVarTuple, TypedDict
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, create_model
from pydantic.fields import ModelPrivateAttr
from openai.types.shared.response_format_json_schema import ResponseFormatJSONSchema, JSONSchema
from openai.types.shared.function_definition import FunctionDefinition
from openai import pydantic_function_tool
from rich import inspect as rich_inspect
from rich.console import Console

from pydantic.json_schema import _get_all_json_refs, _get_typed_dict_config, _make_json_hashable, GenerateJsonSchema


openai = OpenAI()
console = Console()

import re

def uncamelcase(name: str) -> str:
    """
    Convert a camel case string into separate words.
    
    Args:
    name (str): The camel case string.
    
    Returns:
    str: The string with words separated by spaces.
    """
    # Use regex to find boundaries between words
    words = re.findall(r'[A-Z][a-z]*|[a-z]+|\d+', name)
    # Join the words with spaces
    return ' '.join([w.lower() for w in words])



class AcceptOrReject(BaseModel):
    accept: bool
    feedback: str 




class NaturalCoqProof(BaseModel):
    natural: str
    coq: str


import inspect
from inspect import Parameter
from pydantic.fields import FieldInfo
from pydantic.json_schema import JsonSchemaValue

M = TypeVar("M", bound=Type[BaseModel] | FunctionType)

JsonDict = TypedDict("JsonDict", {"$ref": JsonSchemaValue}, total=False)
def openai_schema(model_class: Type[BaseModel],strict=True) -> Dict[str, object]:

    def remove_defaults(schema: Dict[str, object]) -> Dict[str, object]:
        return {k: remove_defaults(v) if isinstance(v, dict) else v for k, v in schema.items() if k != "default"}
    
    def require_all(schema: Dict[str, object], refs: Dict[str, object] | None = None) -> Dict[str, object]:
        if "$ref" in schema and refs is not None:
            require_all(refs[schema["$ref"].split("/")[-1]], refs)
            return schema
        if "properties" not in schema:
            return schema
        if "required" in schema:
            schema["required"] = list(set(schema["required"]) | set(schema["properties"].keys()))
        
        schema["properties"] = {k: require_all(v, refs) if isinstance(v, dict) else v for k, v in schema["properties"].items()}
        return schema

    def remove_additional_properties(schema: JsonDict[str, Any], refs: Dict[str, T] | None = None) -> Dict[str, object]:
        if "$defs" in schema:
            schema["$defs"] = {k: remove_additional_properties(v, refs) if isinstance(v, dict) else v for k, v in schema["$defs"].items()}
        if "$ref" in schema and refs is not None:
            refs = remove_additional_properties(refs[schema["$ref"].split("/")[-1]], refs)
            nonlocal schema_out
            schema_out["$defs"] = refs
            return schema
        if "properties" not in schema:
            return schema

        schema["properties"] = {k: remove_additional_properties(v) if isinstance(v, dict) else v for k, v in schema["properties"].items()}
        return {**schema, "additionalProperties": False}
    schema_out = remove_defaults({**model_class.model_json_schema()})
    if strict:
        schema = require_all(schema_out, schema_out.get("$defs"))
        schema = remove_additional_properties(schema_out, schema_out.get("$defs"))
    return schema

Primative: TypeAlias = Union[float, str, int, bool, dict, list, "Dict", "SampleState", "List", "SampleStr", "SampleFloat", "SampleArray", "SampleDeque"]
T = TypeVar("T", bound=Union[float, str, int, bool, dict, list, "Dict", "SampleState", "List", "SampleStr", "SampleFloat", "SampleArray", "SampleDeque"])
Us = TypeVarTuple("Us")
V = TypeVar("V", bound=Union[float, str, int, bool, dict, list, "Dict", "SampleState", "List", "SampleStr", "SampleFloat", "SampleArray", "SampleDeque"])

if TYPE_CHECKING:
    ParentT = NamedTuple
else:
    ParentT = type(defaultdict)

@dataclass_transform()
class mbdict(ParentT, Generic[ T, *Us, V]):

    
    __pydantic_config__: ClassVar[ConfigDict] = {"arbitrary_types_allowed": True, "defer_build": True, "from_attributes": True}
    def __getattribute__(self, name):
        if not name.startswith("_"):
            return self.get(name)
        return super().__getattribute__(name)
    def __setattr__(self, name, value):
        if not name.startswith("_"):
            self[name] = value
        return super().__setattr__(name, value)


class SampleDict(defaultdict,metaclass=mbdict):
    a: int 
    b: str

a = SampleDict()

class Derived(SampleDict):
    c: float

from numpy import ndarray
from typing import Protocol, Type, TypeVar, Annotated, ParamSpec, Literal, _SpecialForm, ParamSpecKwargs
P = ParamSpec("P")
class HasAnnotations(Protocol[P]):
    __annotations__: ParamSpecKwargs
class DataclassType(HasAnnotations[P]):
    __dataclass_fields__: ParamSpecKwargs = __annotations__

from types import GetSetDescriptorType, MappingProxyType, MemberDescriptorType, DynamicClassAttribute, WrapperDescriptorType
from typing import NamedTuple
sz = Literal

    
@dataclass_transform()
def mbclass(cls: Type[HasAnnotations[P]]) -> Type[HasAnnotations[P]]:
    mbdict.__dataclass_fields__ = {k: v for k, v in cls.__annotations__.items()}
    mbdict.__type_adapter__ = TypeAdapter(cls)
    
    return mbdict

def mbfield(cls: Type[HasAnnotations[P]]) -> Type[HasAnnotations[P]]:
    mbdict.__dataclass_fields__ = dict(cls.__annotations__.items())
    mbdict.__type_adapter__ = TypeAdapter(cls)
    return mbdict
    
class mblist(mbdict, Generic[T, *Us]):...
class mbtuple(mbdict, Generic[T, *Us]):...
class mbdeque(mbdict, Generic[T, *Us]):...

class SampleDict(mbdict[str, T, *Us, V]):...

class SampleState(mbdict):...

class SampleList(mblist):...

class SampleTuple(mbtuple):...

class SampleStr(str):...

class SampleFloat(float):...

class SampleArray(list):...

class SampleDeque(list):...

# class SampleField(mbfield):...


M = TypeVar("M", bound=Primative | object)

class Tool(Dict, Generic[M]):
    model: ClassVar[Type[M] | None] = None
    _schema_generator: GenerateJsonSchema = GenerateJsonSchema
    arguments: Dict[str, M] | None = None
    
    
        
    def __class_getitem__(cls, item: M | FunctionType) -> Type[Self]:
        if isinstance(item, FunctionType):
            params = inspect.signature(item).parameters
            required = {k for k, v in params.items() if v.default == Parameter.empty}
            if any(v.annotation == Parameter.empty for v in params.values()):
                raise ValueError("All parameters must have type hints.")
            if not item.__name__ and not item.__qualname__:
                raise ValueError("Function must have a name.")
            print(item.__name__)
            basemodel = create_model(
                cls._schema_generator().get_title_from_name(name=item.__name__).replace(" ", ""),
                **{
                    k: (
                        v.annotation,
                        FieldInfo.from_annotation(v.annotation)
                        if v.default == Parameter.empty
                        else FieldInfo.from_annotated_attribute(v.annotation, v.default),
                    )
                    for k, v in params.items()
                },
            )
            item = basemodel
        elif not issubclass(item, BaseModel):
            raise ValueError("Item must be a BaseModel subclass or a function.")
        else:
            required = {
                k for k, v in inspect.signature(item.__init__).parameters.items() if v.default == Parameter.empty
            }

        if not required:
            raise ValueError("At least one required parameter or base model field is required.")
        cls.model = item
        return cls
    

    @classmethod
    def json_schema(cls, strict: bool | None = None) -> JSONSchema:
        model_class = cls.model
        strict = strict if strict is not None else model_class.model_config.get("strict", False)
        return JSONSchema(
            name=cls._schema_generator().get_title_from_name(model_class.__name__).replace(" ", ""),
            description=model_class.__doc__ or uncamelcase(model_class.__name__),
            schema=openai_schema(model_class),
            strict=strict,
        )

    @classmethod
    def response_format(cls,*, strict: bool | None = None) -> Dict[str, str]:
        return ResponseFormatJSONSchema(
            json_schema=cls.json_schema(strict),
            type="json_schema",
        ).model_dump(by_alias=True)
    
    @classmethod
    def get_name(cls) -> str:
        return cls._schema_generator().get_title_from_name(cls.model.__name__).replace(" ", "")


    
    @classmethod
    def define(cls,*, strict: bool | None = None) -> Dict[str, object]:
        strict =  strict if strict is not None  else cls.model.model_config.get("strict", False)
        parameters = cls.model.model_json_schema() if not strict else openai_schema(cls.model)
        name = cls.get_name()

        return {
            "type": "function",
            "function": FunctionDefinition(name=name, parameters=parameters,strict=strict).model_dump(by_alias=True),
        }

    @classmethod
    def call(cls, arguments: Dict[str, M] | None = None) -> M:
        return cls.model.model_validate_json(arguments)

    @classmethod
    def prompt(cls, system: str | None = None) -> str:
        model_class = cls.model
        model_doc = model_class.__doc__.strip() if model_class.__doc__ else ""
        doc = model_doc[:1].lower() + model_doc[1:] if model_doc else ""
        if doc.startswith("a ") or doc.startswith("an ") or doc.startswith("the "):
            pass
        elif doc:
            doc = "the " + doc
        else:
            doc = "a " + uncamelcase(model_class.__name__)
        system = system or "Respond with " + doc + ". DO NOT leave out any required items!"

        examples = ""
        for k, v in model_class.model_fields.items():
            if v.examples is not None:
                examples += f"\t - **{k}**: {v.examples}\n"
        examples = f"Here are some examples:\n{examples}" if examples else ""
        return f"{system}\n{examples}"

from base64 import b64decode


def accept_or_reject(accept: AcceptOrReject, further_comments: str = ""):
    return {"accept": accept, "further_comments": further_comments}

print(
    Tool[accept_or_reject].prompt(),
)
print(Tool[accept_or_reject].response_format())
print(Tool[accept_or_reject].define())

console.print(Tool[accept_or_reject].define())
console.print(Tool[accept_or_reject].define(strict=True))



console.print(Tool[accept_or_reject].define())
console.print(Tool[accept_or_reject].define(strict=True))
resp = openai.beta.assistants.list(limit=100)
from datetime import datetime

for assistant in sorted(resp.data, key=lambda x: x.created_at, reverse=True):
    console.print(assistant.id, assistant.name, assistant.tool_resources, assistant.model, datetime.fromtimestamp(assistant.created_at))

resp = openai.beta.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[
        {
            "role": "system",
            "content": Tool[accept_or_reject].prompt(),
        },
    ],
    response_format=Tool[accept_or_reject].response_format(),
)
rich_inspect(resp)

rp = Tool[accept_or_reject].call(resp.choices[0].message.content)
rich_inspect(rp)
from openai import AsyncOpenAI
from uvloop import install
import asyncio
install()
aopenai = AsyncOpenAI()
tc = None

async def aact_structured(tool: Type[Tool], system_prompt: str | None = None, *,structured_type: Literal["response_format", "tool_call"] = "response_format") -> str:

    async with aopenai.beta.chat.completions.stream(
        model="gpt-4o-2024-08-06",
        messages= system_prompt + [
            {
                "role": "system",
                "content":  system_prompt or tool.prompt(),
            },
        ] if isinstance(system_prompt, list) else [
            {
                "role": "system",
                "content":  system_prompt or tool.prompt(),
            },
        ],
            ) as stream:
            text = ""
            tool = ""
            async for event in stream:
                if event.type == "content.delta":
                    text += event.delta
                    console.print(text, end="")
                if event.type == "content.done":
                    text = event.content
                    console.print(text, end="")
                if event.type == "tool_calls.function.arguments.delta":
                    tool += event.arguments_delta
                    console.print(text, end="")
                if event.type == "tool_calls.function.arguments.done":
                    tool = event.arguments
                    console.print(tool, new_line_start=True)
                    tc = Tool[accept_or_reject].call(event.arguments)
                    console.print(tc, new_line_start=True)
            input("Press Enter to continue...")

def act(tool: Type[Tool], system_prompt: str | None = None, *,structured_type: Literal["response_format", "tool_call"] = "response_format") -> str:
    return asyncio.run(aact_structured(tool, system_prompt, structured_type=structured_type))


                
# resp = openai.beta.chat.completions.stream(
#     model="gpt-4o-realtime-preview-2024-10-01",
#     messages=[
#         {
#             "role": "system",
#             "content": Tool[accept_or_reject].prompt(),
#         }
#     ],
#     tool_choice="required",
#     tools=[Tool[accept_or_reject].define(strict=True)],
# )
# rich_inspect(resp.choices[0].message.tool_calls[0].function.arguments)
# tc = Tool[accept_or_reject].call(resp.choices[0].message.tool_calls[0].function.arguments)
# rich_inspect(tc)


# class Tool(BaseModel):
#     type: str = "function"
#     function: Dict[str, T] = Field(default_factory=dict)

# args = response.choices[0].message.tool_calls[0].function.arguments
# accepted = AcceptOrReject.model_validate_json(args)


class Prover:
    """An agent that uses an interactive theorem prover to generate proofs."""

    def __init__(
        self,
        goal: str,
        system_prompt_or_path: str = "Respond with a Coq proof that can be split into natural language and Coq code. Respond with the format: <natural language>\n```\n<Coq code>\n```",
        model: str = "gpt-4o",
    ):
        self._model = model
        self._context: List[Dict[str, str]] = []

        if Path(system_prompt_or_path).exists():
            self._context.append({"role": "system", "content": Path(system_prompt_or_path).read_text()})
        else:
            self._context.append({"role": "system", "content": system_prompt_or_path})

        # Add the goal to the context
        self._context.append({"role": "user", "content": goal})

    def _call_model(self, temperature: float = 0.5) -> str:
        """Call the model with the current context."""
        response = openai.chat.completions.create(
            model=self._model,
            messages=self._context,
            temperature=temperature,
        )
        return response.choices[0].message.content

    def step(self, input: str | None) -> Tuple[str, str]:  # noqa
        if input is not None:
            # Add the user input to the context
            self._context.append({"role": "user", "content": input})

        while True:
            model_output = self._call_model()
            print(f"Raw model output: {model_output}")

            # Add the model output to the context
            self._context.append({"role": "assistant", "content": model_output})
            return act(Tool[NaturalCoqProof], self._context)
            try:
                # Split on code:
                # split = model_output.split("```\n")
                # natural = split[0]
                # coq = split[1]

                match = re.search(r"```(?:\w+\n)?(.*?)```", model_output, re.DOTALL)
                if not match:
                    raise ValueError("The model output should contain exactly one code block.")
                natural = model_output.split("```")[0].strip()
                coq = match.group(1).strip()

                break
            except (IndexError, ValueError, AttributeError) as e:
                # Step again, but remind the model to use the format.
                traceback.print_exc()
                self._context.append(
                    {
                        "role": "user",
                        "content": "You caused an error: "
                        + traceback.format_exc()
                        + " Please use the specified format. Do not leave out any of the sections. Do not add any additional output.",
                    }
                )
                continue

        return natural, coq


class Checker:
    """A stateless agent that evaluates the proofs generated by the prover."""

    def __init__(
        self,
        system_prompt_or_path: str = "Check the natural language and math proof of the statement only. Provide feedback if incorrect.",
        model: str = "gpt-4o",
    ):
        self._model = model
        if Path(system_prompt_or_path).exists():
            self._system_prompt = Path(system_prompt_or_path).read_text()
        else:
            self._system_prompt = system_prompt_or_path

    def check(self, input: str) -> Tuple[str, bool]:  # noqa
        """Return feedback on the proof."""
        accept_tool = {
            "type": "function",
            "function": {
                "name": "accept_or_reject",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "accept": {"type": "boolean"},
                        "feedback": {"type": "string"},
                    },
                    "required": ["accept"],
                },
            },
        }
        response = openai.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": input},
            ],
            tools=[accept_tool],
            tool_choice="required",
        )

        class AcceptOrReject(BaseModel):
            accept: bool
            feedback: str = ""

        args = response.choices[0].message.tool_calls[0].function.arguments
        accepted = AcceptOrReject.model_validate_json(args)

        # Check if the proof is ACCEPTED

        return accepted.feedback, accepted.accept
