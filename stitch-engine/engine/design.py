"""The design JSON contract, written as Pydantic models.

FastAPI uses these to validate request bodies, so a malformed design gets a
clear 422 error that names the bad field instead of a crash deep in the
engine. Field names are camelCase on purpose so they match the JSON (and
your TypeScript types) one-to-one.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, FiniteFloat, model_validator

# One [x, y] point in mm. FiniteFloat rejects NaN and Infinity.
Point = tuple[FiniteFloat, FiniteFloat]


class Hoop(BaseModel):
    widthMm: float = Field(gt=0)
    heightMm: float = Field(gt=0)


class Backdrop(BaseModel):
    """The tracing image shown behind the design in the editor.

    The engine never stitches it; it is accepted so a full design file
    validates.
    """

    uri: str | None = None
    xMm: float = 0
    yMm: float = 0
    scale: float = 1
    rotation: float = 0
    opacity: float = 1
    locked: bool = False
    visible: bool = True


class Thread(BaseModel):
    id: str
    name: str = ""
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class BaseObject(BaseModel):
    """Fields every stitch object shares."""

    id: str
    threadId: str
    path: list[Point] = Field(min_length=2)
    closed: bool = False
    locked: bool = False  # editor-only, ignored by the engine
    visible: bool = True  # hidden objects are not stitched


# --- Running stitch -------------------------------------------------------


class RunningProps(BaseModel):
    stitchLengthMm: float = Field(2.5, ge=0.5, le=12)
    # 1 = plain running stitch, 3 = bean stitch (every stitch sewn
    # forward, back, forward for a bolder line).
    passes: Literal[1, 3] = 1


class RunningObject(BaseObject):
    type: Literal["running"]
    props: RunningProps = Field(default_factory=RunningProps)


# --- The whole design -----------------------------------------------------

# Pydantic picks the right object class by looking at the "type" field.
DesignObject = Annotated[Union[RunningObject], Field(discriminator="type")]


class Design(BaseModel):
    version: Literal[1] = 1
    name: str = "Untitled"
    hoop: Hoop = Field(default_factory=lambda: Hoop(widthMm=100, heightMm=100))
    backdrop: Backdrop | None = None
    threads: list[Thread] = Field(min_length=1)
    # Objects are sewn in list order.
    objects: list[DesignObject] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_references(self) -> "Design":
        thread_ids = {t.id for t in self.threads}
        seen = set()
        for obj in self.objects:
            if obj.threadId not in thread_ids:
                raise ValueError(f"object {obj.id!r} uses unknown threadId {obj.threadId!r}")
            if obj.id in seen:
                raise ValueError(f"duplicate object id {obj.id!r}")
            seen.add(obj.id)
        return self

    def thread(self, thread_id: str) -> Thread:
        return next(t for t in self.threads if t.id == thread_id)
