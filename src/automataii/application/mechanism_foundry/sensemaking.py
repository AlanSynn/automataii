"""Mechanism Foundry sensemaking models and rules for novice-facing feedback."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .mechanism_types import canonical_mechanism_type


@dataclass(frozen=True)
class CauseEffectRule:
    """One inspectable mechanism edit and the motion consequence it foregrounds."""

    mechanism_type: str
    parameter_key: str
    parameter_label: str
    role: str
    cause_label: str
    effect_label: str
    principle: str
    build_hint: str
    prompt: str
    confidence: str = "high"


@dataclass(frozen=True)
class MechanismStory:
    """Compact story used when no parameter has changed yet."""

    mechanism_type: str
    title: str
    focus: str
    chain: str
    motion_question: str
    kit_move: str


@dataclass(frozen=True)
class SensemakingMotionPoint:
    """A mechanism point and the state key used for explanation evidence."""

    label: str
    value: str
    state_key: str
    evidence_label: str | None = None
    selectable: bool = True

    @property
    def snapshot_label(self) -> str:
        """Short label used inside evidence sentences."""
        return self.evidence_label or self.label


@dataclass(frozen=True)
class SensemakingPointSnapshot:
    """Lightweight mechanism point evidence for the current preview state."""

    key: str
    label: str
    x: float
    y: float
    previous_x: float | None = None
    previous_y: float | None = None

    @property
    def summary(self) -> str:
        return f"{self.label}≈({self.x:.0f}, {self.y:.0f})"

    @property
    def movement_mm(self) -> float | None:
        if self.previous_x is None or self.previous_y is None:
            return None
        return math.hypot(self.x - self.previous_x, self.y - self.previous_y)


@dataclass(frozen=True)
class SensemakingParameterChange:
    """Formatted before/after parameter change for a learner-facing context."""

    parameter_key: str
    parameter_label: str
    before_value: str
    after_value: str

    @property
    def summary(self) -> str:
        return f"{self.parameter_label}: {self.before_value} → {self.after_value}"


@dataclass(frozen=True)
class SensemakingContext:
    """Application-owned explanation state for the Foundry sensemaking panel."""

    mechanism_type: str
    story: MechanismStory
    selected_motion_point_label: str
    selected_motion_point_key: str | None
    change: SensemakingParameterChange | None
    cause_line: str
    effect_line: str
    principle_line: str
    watch_line: str
    evidence_line: str
    build_check: str
    teacher_prompt: str
    point_snapshots: tuple[SensemakingPointSnapshot, ...] = ()
    confidence: str = "high"
    evidence_pending: bool = False

    @property
    def change_line(self) -> str:
        if self.change is None:
            return "Pick one slider. Predict first, then compare the trace."
        return self.change.summary


@dataclass(frozen=True)
class SensemakingPreviewSnapshot:
    """Atomic preview evidence supplied by the UI after or before a render pass.

    `geometry_pending=True` means the learner-facing context may show the parameter
    change immediately, but should not claim that the rendered point positions are
    already current.
    """

    current_parameters: Mapping[str, object]
    current_positions: Mapping[str, object] | None = None
    previous_positions: Mapping[str, object] | None = None
    geometry_pending: bool = False


@dataclass(frozen=True)
class FoundrySensemakingEvent:
    """Legacy event shape retained for tests and older panel call sites."""

    mechanism_type: str
    parameter_key: str
    parameter_label: str
    before_value: str
    after_value: str
    selected_motion_point: str
    evidence_summary: str


class SensemakingService:
    """Build learner-friendly cause/effect contexts from raw Foundry state.

    The service intentionally uses explicit, conservative rules instead of generated text.
    That keeps the learning scaffold teachable: one part change, one motion consequence,
    one physical-build hint, and one reflection prompt.
    """

    _UNKNOWN_RULE = CauseEffectRule(
        mechanism_type="unknown",
        parameter_key="unknown",
        parameter_label="Parameter",
        role="Editable part",
        cause_label="A part value changed.",
        effect_label="Look for the motion feature that changes most clearly.",
        principle="Mechanism motion comes from geometry, contact, and assembly constraints.",
        build_hint="Mark one change on the kit before rebuilding so learners compare one variable.",
        prompt="Which point moved differently after this one change?",
        confidence="unknown",
    )

    _STORIES: dict[str, MechanismStory] = {
        "four_bar": MechanismStory(
            mechanism_type="four_bar",
            title="Four-bar linkage",
            focus="A crank pushes a middle bar, then the output arm swings.",
            chain="input crank → coupler path → output rocker",
            motion_question="Which joint path best matches the character action?",
            kit_move="Move one hole at a time on the bar-board, then compare the traces.",
        ),
        "cam_follower": MechanismStory(
            mechanism_type="cam_follower",
            title="Cam and follower",
            focus="A rotating cam lifts a follower up and down.",
            chain="cam shape → contact height → follower lift",
            motion_question="Does the lift feel like a bounce, flap, nod, or hesitation?",
            kit_move="Swap or offset the cam, then check whether friction changes the lift.",
        ),
        "gear_train": MechanismStory(
            mechanism_type="gear_train",
            title="Gear train",
            focus="Meshing teeth trade speed, direction, and effort.",
            chain="drive gear teeth → ratio → driven gear speed",
            motion_question="Should the character move faster, slower, or the other way?",
            kit_move="Count teeth before assembly and leave spacer clearance for free rotation.",
        ),
        "gear_linkage": MechanismStory(
            mechanism_type="gear_linkage",
            title="Gear + linkage",
            focus="A driven gear carries an off-center pin that pulls a linkage arm.",
            chain="gear ratio → crank pin orbit → linkage swing",
            motion_question="Does the linkage need a bigger swing, different timing, or less force?",
            kit_move="Use a 4 mm crank hole and a loose bracket so the link can rotate freely.",
        ),
        "planetary_gear": MechanismStory(
            mechanism_type="planetary_gear",
            title="Planetary gear",
            focus="A sun gear drives orbiting planets held by a carrier arm.",
            chain="sun teeth → planet orbit → carrier/output point",
            motion_question="Should the motion feel compact, orbital, or geared-down?",
            kit_move="Pin the sun first, then add the carrier and planet with loose spacers.",
        ),
        "slider_crank": MechanismStory(
            mechanism_type="slider_crank",
            title="Slider-crank",
            focus="A crank turns rotation into a straight push-pull motion.",
            chain="crank radius → rod angle → slider stroke",
            motion_question="What expressive beat needs a straight push or pull?",
            kit_move="Use the guide slot to compare stroke before adding the character piece.",
        ),
    }

    _POINT_SPECS: dict[str, tuple[SensemakingMotionPoint, ...]] = {
        "four_bar": (
            SensemakingMotionPoint("Joint A (Input)", "joint_a", "A", "Joint A"),
            SensemakingMotionPoint("Joint B (Output)", "joint_b", "B", "Joint B"),
        ),
        "cam_follower": (
            SensemakingMotionPoint(
                "Follower Base",
                "follower_base",
                "follower_base",
                "Follower base",
            ),
            SensemakingMotionPoint(
                "Contact Point",
                "contact_point",
                "contact_point",
                "Contact point",
            ),
        ),
        "gear_train": (
            SensemakingMotionPoint(
                "Drive gear",
                "gear1_center",
                "gear1_center",
                selectable=False,
            ),
            SensemakingMotionPoint(
                "Driven gear",
                "gear2_center",
                "gear2_center",
                selectable=False,
            ),
        ),
        "gear_linkage": (
            SensemakingMotionPoint("Linkage pin", "linkage_pin", "linkage_pin", "Linkage pin"),
            SensemakingMotionPoint(
                "Linkage end",
                "linkage_end",
                "linkage_end",
                "Linkage end",
            ),
        ),
        "planetary_gear": (
            SensemakingMotionPoint("Planet center", "planet_center", "planet_center", "Planet"),
            SensemakingMotionPoint(
                "Output pin",
                "tracking_point",
                "tracking_point",
                "Output pin",
            ),
        ),
        "slider_crank": (
            SensemakingMotionPoint(
                "Crank pin",
                "crank_end",
                "crank_end",
                selectable=False,
            ),
            SensemakingMotionPoint(
                "Slider pin",
                "slider_pin",
                "slider_pin",
                selectable=False,
            ),
        ),
    }

    _RULES: dict[tuple[str, str], CauseEffectRule] = {
        ("four_bar", "ground_link"): CauseEffectRule(
            mechanism_type="four_bar",
            parameter_key="ground_link",
            parameter_label="Ground link",
            role="Fixed pivot spacing",
            cause_label="You moved the two fixed pivots farther apart or closer together.",
            effect_label="The output arm can swing through a different range.",
            principle="Fixed pivots set the linkage constraint before the bars move.",
            build_hint="On the bar-board, compare the two anchored fastener holes.",
            prompt="Did the output swing get wider, narrower, or stuck?",
        ),
        ("four_bar", "input_link"): CauseEffectRule(
            mechanism_type="four_bar",
            parameter_key="input_link",
            parameter_label="Input link",
            role="Input crank radius",
            cause_label="You changed the radius of the crank you turn.",
            effect_label="Joint A travels on a larger or smaller circle.",
            principle="A larger input radius sends a larger motion into the coupler.",
            build_hint="Use one different hole on the input bar and keep the ground pivot fixed.",
            prompt="Which character motion became more exaggerated?",
        ),
        ("four_bar", "coupler_link"): CauseEffectRule(
            mechanism_type="four_bar",
            parameter_key="coupler_link",
            parameter_label="Coupler link",
            role="Motion transfer bar",
            cause_label="You changed the bar that carries motion across the linkage.",
            effect_label="The middle path can bend into a different gesture.",
            principle="The coupler constrains both moving joints at the same time.",
            build_hint="Check that both coupler holes line up without bending the paper.",
            prompt="Does the gesture now look smoother, sharper, or wobblier?",
        ),
        ("four_bar", "output_link"): CauseEffectRule(
            mechanism_type="four_bar",
            parameter_key="output_link",
            parameter_label="Output link",
            role="Visible rocker arm",
            cause_label="You changed the bar that swings the output point.",
            effect_label="The final arm can reach a different set of poses.",
            principle="Output length turns the coupler pull into an arc around the fixed pivot.",
            build_hint="Check that the output bar clears the board and spacers before adding a limb.",
            prompt="Can a student explain why the final pose changed?",
        ),
        ("cam_follower", "cam_radius"): CauseEffectRule(
            mechanism_type="cam_follower",
            parameter_key="cam_radius",
            parameter_label="Cam radius",
            role="Base cam size",
            cause_label="You changed the cam's overall size.",
            effect_label="The follower starts higher or lower relative to the axle.",
            principle="A follower reads distance from the cam center as height.",
            build_hint="Make sure the larger cam clears the frame and follower guide.",
            prompt="Did lift amount, contact timing, or both change?",
        ),
        ("cam_follower", "cam_offset"): CauseEffectRule(
            mechanism_type="cam_follower",
            parameter_key="cam_offset",
            parameter_label="Cam offset",
            role="Lift amplitude",
            cause_label="You moved the cam's high side farther from the center.",
            effect_label="The follower rises and drops more noticeably.",
            principle="Offset turns rotation into repeated vertical lift.",
            build_hint="Add a spacer washer so the offset cam does not scrape.",
            prompt="Does the lift read as surprise, jump, or hesitation?",
        ),
        ("cam_follower", "follower_length"): CauseEffectRule(
            mechanism_type="cam_follower",
            parameter_key="follower_length",
            parameter_label="Follower length",
            role="Guided output rod",
            cause_label="You changed the rod that carries the lift to the character.",
            effect_label="The same lift appears at a different height or clearance.",
            principle="The cam sets displacement; the follower positions where it appears.",
            build_hint="Keep the guide straight; a long paper rod can buckle.",
            prompt="Is the problem motion shape or where the motion reaches?",
        ),
        ("cam_follower", "cam_lobes"): CauseEffectRule(
            mechanism_type="cam_follower",
            parameter_key="cam_lobes",
            parameter_label="Cam lobes",
            role="Rhythm count",
            cause_label="You changed how many high points the cam has per turn.",
            effect_label="The follower can lift more times during one handle turn.",
            principle="Each lobe repeats the contact-height pattern.",
            build_hint="Laminate multi-lobe cams because narrow peaks wear down quickly.",
            prompt="Should the action happen once, twice, or as a repeated beat?",
        ),
        ("cam_follower", "profile_harmonic"): CauseEffectRule(
            mechanism_type="cam_follower",
            parameter_key="profile_harmonic",
            parameter_label="Profile variation",
            role="Cam contour sharpness",
            cause_label="You changed how far the cam shape departs from a circle.",
            effect_label="The lift can feel softer or more dramatic.",
            principle="Smooth contours spread lift; sharper contours concentrate it.",
            build_hint="Avoid sharp paper peaks that catch on the follower.",
            prompt="Does the action need a soft rise or a comic pop?",
        ),
        ("gear_train", "gear1_teeth"): CauseEffectRule(
            mechanism_type="gear_train",
            parameter_key="gear1_teeth",
            parameter_label="Drive gear teeth",
            role="Input gear size",
            cause_label="You changed the gear turned by the handle.",
            effect_label="The output gear speed ratio changes.",
            principle="Meshed gears trade speed by tooth-count ratio.",
            build_hint="Match center distance to gear size so paper teeth do not bind.",
            prompt="Is the learner explaining speed, direction, or effort?",
        ),
        ("gear_train", "gear2_teeth"): CauseEffectRule(
            mechanism_type="gear_train",
            parameter_key="gear2_teeth",
            parameter_label="Driven gear teeth",
            role="Output gear size",
            cause_label="You changed the gear that receives the motion.",
            effect_label="The output turns more or fewer degrees per handle turn.",
            principle="A larger driven gear turns fewer degrees per input rotation.",
            build_hint="Use spacers so both gears mesh without rubbing the board.",
            prompt="Is slower motion useful for suspense or careful movement?",
        ),
        ("gear_train", "input_torque"): CauseEffectRule(
            mechanism_type="gear_train",
            parameter_key="input_torque",
            parameter_label="Input torque",
            role="Handle effort",
            cause_label="You changed the turning effort applied to the handle.",
            effect_label="The path shape stays the same, but the build may feel easier or harder.",
            principle="Gear geometry sets motion ratio; torque helps overcome load and friction.",
            build_hint="If gears stall, reduce decoration load or improve axle spacing first.",
            prompt="Is the issue motion shape, effort, or friction?",
        ),
        ("gear_linkage", "gear1_teeth"): CauseEffectRule(
            mechanism_type="gear_linkage",
            parameter_key="gear1_teeth",
            parameter_label="Drive gear teeth",
            role="Input gear size",
            cause_label="You changed the gear turned by the handle.",
            effect_label="The crank pin timing and driven gear ratio change together.",
            principle="The first gear sets how quickly the crank pin orbits.",
            build_hint="Pick a compatible gear pair on the board before attaching the linkage.",
            prompt="Did the linkage swing faster, slower, or with different timing?",
        ),
        ("gear_linkage", "gear2_teeth"): CauseEffectRule(
            mechanism_type="gear_linkage",
            parameter_key="gear2_teeth",
            parameter_label="Driven gear teeth",
            role="Crank gear size",
            cause_label="You changed the gear carrying the off-center linkage pin.",
            effect_label="The linkage receives a different crank speed and leverage.",
            principle="Driven gear size changes both rotation ratio and available crank placement.",
            build_hint="Use spacers so the crank gear clears the linkage bracket.",
            prompt="Is the output better as a quick flutter or a slower pull?",
        ),
        ("gear_linkage", "linkage_pin_radius"): CauseEffectRule(
            mechanism_type="gear_linkage",
            parameter_key="linkage_pin_radius",
            parameter_label="Linkage pin radius",
            role="Crank throw",
            cause_label="You moved the linkage pin farther from or closer to the gear center.",
            effect_label="The linkage end travels through a larger or smaller swing.",
            principle="Off-center pin radius turns rotation into reciprocating linkage motion.",
            build_hint="Choose a handle/linkage hole on the gear and keep the fastener loose.",
            prompt="Which pin hole gives the clearest character gesture?",
        ),
        ("gear_linkage", "linkage_arm_length"): CauseEffectRule(
            mechanism_type="gear_linkage",
            parameter_key="linkage_arm_length",
            parameter_label="Linkage arm length",
            role="Output arm reach",
            cause_label="You changed the bar pulled by the crank pin.",
            effect_label="The same crank motion reaches a different character anchor point.",
            principle="A longer linkage carries motion farther but can add side load.",
            build_hint="Check the linkage clears neighboring gears, brackets, and spacers.",
            prompt="Did length solve reach, or did it introduce rubbing?",
        ),
        ("planetary_gear", "sun_teeth"): CauseEffectRule(
            mechanism_type="planetary_gear",
            parameter_key="sun_teeth",
            parameter_label="Sun gear teeth",
            role="Central gear size",
            cause_label="You changed the gear in the middle of the planetary set.",
            effect_label="The planet orbit and carrier speed relationship changes.",
            principle="Sun and planet tooth counts set the compact gear ratio.",
            build_hint="Keep the sun axle straight before adding the carrier.",
            prompt="Does the output need stronger reduction or quicker orbital motion?",
        ),
        ("planetary_gear", "planet_teeth"): CauseEffectRule(
            mechanism_type="planetary_gear",
            parameter_key="planet_teeth",
            parameter_label="Planet gear teeth",
            role="Orbiting gear size",
            cause_label="You changed the gears riding around the sun.",
            effect_label="The carrier needs a different orbit radius and mesh spacing.",
            principle="Planet size determines both tooth ratio and physical spacing.",
            build_hint="Choose planets that still fit on the same board neighborhood.",
            prompt="Did the new planet size improve compactness or make spacing harder?",
        ),
        ("planetary_gear", "planet_count"): CauseEffectRule(
            mechanism_type="planetary_gear",
            parameter_key="planet_count",
            parameter_label="Planet count",
            role="Load sharing",
            cause_label="You changed how many planets ride on the carrier.",
            effect_label="The visual motion becomes more balanced, but assembly needs more pins.",
            principle="More planets share load but add alignment constraints.",
            build_hint="Prototype with one planet first, then mirror additional planets.",
            prompt="Is balance worth the extra assembly complexity here?",
        ),
        ("planetary_gear", "carrier_arm_length"): CauseEffectRule(
            mechanism_type="planetary_gear",
            parameter_key="carrier_arm_length",
            parameter_label="Carrier handle length",
            role="Output reach",
            cause_label="You changed the handle hole extending from the carrier.",
            effect_label="The output pin reaches a larger or smaller character anchor area.",
            principle="Carrier reach affects where compact orbital motion can be delivered.",
            build_hint="Use a loose paper fastener at the carrier handle hole.",
            prompt="Does the handle reach the character without rubbing the planets?",
        ),
        ("slider_crank", "crank_length"): CauseEffectRule(
            mechanism_type="slider_crank",
            parameter_key="crank_length",
            parameter_label="Crank length",
            role="Stroke radius",
            cause_label="You changed the radius of the rotating crank.",
            effect_label="The slider usually moves a longer or shorter distance.",
            principle="Slider stroke is mainly twice the crank radius.",
            build_hint="Check the slot is long enough before attaching a character piece.",
            prompt="What story action needs a longer straight push?",
        ),
        ("slider_crank", "rod_length"): CauseEffectRule(
            mechanism_type="slider_crank",
            parameter_key="rod_length",
            parameter_label="Rod length",
            role="Connecting rod constraint",
            cause_label="You changed the rod between crank and slider.",
            effect_label="The slider stays straight, but smoothness and side force can change.",
            principle="The rod resolves circular motion into a constrained linear guide.",
            build_hint="A short rod can jam unless the guide is loose and straight.",
            prompt="Did this edit fix timing, smoothness, or jamming?",
        ),
        ("slider_crank", "gas_pressure"): CauseEffectRule(
            mechanism_type="slider_crank",
            parameter_key="gas_pressure",
            parameter_label="Gas pressure",
            role="Output load cue",
            cause_label="You changed the simulated load on the slider.",
            effect_label="The path stays the same, but the story shifts toward stronger pushing.",
            principle="Geometry sets displacement; load describes how much effort it must deliver.",
            build_hint="For a heavy character part, loosen the guide and reduce rubbing first.",
            prompt="Should learners explain path shape, effort, or friction recovery?",
        ),
    }

    @classmethod
    def story_for(cls, mechanism_type: str) -> MechanismStory:
        """Return the baseline story for a mechanism family."""
        normalized = cls._normalize_mechanism_type(mechanism_type)
        return cls._STORIES.get(
            normalized,
            MechanismStory(
                mechanism_type=normalized or "unknown",
                title=(normalized or "mechanism").replace("_", " ").title(),
                focus="Change one part, predict the motion, then test it physically.",
                chain="part geometry → motion path → character action",
                motion_question="Which visible motion changed after the edit?",
                kit_move="Build the smallest comparable version before decorating the automaton.",
            ),
        )

    @classmethod
    def motion_point_options_for(cls, mechanism_type: str) -> tuple[SensemakingMotionPoint, ...]:
        """Return selectable motion points for a mechanism family."""
        normalized = cls.normalize_mechanism_type(mechanism_type)
        return tuple(point for point in cls._POINT_SPECS.get(normalized, ()) if point.selectable)

    @classmethod
    def default_motion_point_for(cls, mechanism_type: str) -> SensemakingMotionPoint | None:
        """Return the default motion point, preferring the visible output point."""
        normalized = cls.normalize_mechanism_type(mechanism_type)
        options = cls.motion_point_options_for(normalized)
        if not options:
            return None
        if normalized == "four_bar" and len(options) > 1:
            return options[1]
        return options[0]

    @classmethod
    def motion_point_for_value(
        cls,
        mechanism_type: str,
        value: str | None,
    ) -> SensemakingMotionPoint | None:
        """Resolve a motion-point selector value."""
        options = cls.motion_point_options_for(mechanism_type)
        for option in options:
            if option.value == value:
                return option
        return cls.default_motion_point_for(mechanism_type)

    @classmethod
    def rule_for(cls, mechanism_type: str, parameter_key: str) -> CauseEffectRule:
        """Return the best available cause-effect rule for the edit."""
        normalized_type = cls._normalize_mechanism_type(mechanism_type)
        normalized_key = str(parameter_key or "").strip().lower()
        rule = cls._RULES.get((normalized_type, normalized_key))
        if rule is not None:
            return rule
        return cls._UNKNOWN_RULE

    @classmethod
    def build_context(
        cls,
        mechanism_type: str,
        selected_motion_point_key: str | None = None,
        selected_motion_point_label: str | None = None,
        parameter_change: SensemakingParameterChange | None = None,
        current_parameters: Mapping[str, object] | None = None,
        current_positions: Mapping[str, object] | None = None,
        previous_positions: Mapping[str, object] | None = None,
        preview_snapshot: SensemakingPreviewSnapshot | None = None,
    ) -> SensemakingContext:
        """Build the application-owned context shown by the right panel."""
        normalized = cls.normalize_mechanism_type(mechanism_type)
        story = cls.story_for(normalized)
        point = cls.motion_point_for_value(normalized, selected_motion_point_key)
        point_label = selected_motion_point_label or (point.label if point else "preview trace")
        point_key = selected_motion_point_key or (point.value if point else None)
        evidence_pending = bool(preview_snapshot and preview_snapshot.geometry_pending)
        if preview_snapshot is not None:
            current_parameters = preview_snapshot.current_parameters
            current_positions = preview_snapshot.current_positions
            previous_positions = preview_snapshot.previous_positions
        if evidence_pending:
            current_positions = None
        snapshots = cls._point_snapshots_for(normalized, current_positions, previous_positions)
        watch_line, evidence_line = cls._watch_and_evidence_line(
            normalized,
            point,
            point_label,
            current_parameters or {},
            snapshots,
            evidence_pending,
        )

        if parameter_change is None:
            return SensemakingContext(
                mechanism_type=normalized,
                story=story,
                selected_motion_point_label=point_label,
                selected_motion_point_key=point_key,
                change=None,
                cause_line="Start with one part change.",
                effect_line=story.focus,
                principle_line=story.motion_question,
                watch_line=watch_line,
                evidence_line=evidence_line,
                build_check=story.kit_move,
                teacher_prompt="Ask: What changed after only one variable moved?",
                point_snapshots=snapshots,
                evidence_pending=evidence_pending,
            )

        rule = cls.rule_for(normalized, parameter_change.parameter_key)
        return SensemakingContext(
            mechanism_type=normalized,
            story=story,
            selected_motion_point_label=point_label,
            selected_motion_point_key=point_key,
            change=parameter_change,
            cause_line=rule.cause_label,
            effect_line=rule.effect_label,
            principle_line=f"{rule.role}: {rule.principle}",
            watch_line=watch_line,
            evidence_line=evidence_line,
            build_check=rule.build_hint,
            teacher_prompt=rule.prompt,
            point_snapshots=snapshots,
            confidence=rule.confidence,
            evidence_pending=evidence_pending,
        )

    @staticmethod
    def format_value(value: object, unit: str | None = None) -> str:
        """Format UI values without exposing Python internals to learners."""
        suffix = f" {unit}" if unit else ""
        if isinstance(value, bool) or value is None:
            return "—"
        if isinstance(value, int):
            return f"{value}{suffix}"
        if isinstance(value, float):
            if not math.isfinite(value):
                return "—"
            if value.is_integer():
                return f"{int(value)}{suffix}"
            return f"{value:.1f}{suffix}"
        try:
            numeric = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            text = str(value).strip()
            return text or "—"
        if not math.isfinite(numeric):
            return "—"
        if numeric.is_integer():
            return f"{int(numeric)}{suffix}"
        return f"{numeric:.1f}{suffix}"

    @classmethod
    def context_from_event(cls, event: FoundrySensemakingEvent) -> SensemakingContext:
        """Convert the P0 event shape into a P1 context for compatibility."""
        change = SensemakingParameterChange(
            parameter_key=event.parameter_key,
            parameter_label=event.parameter_label,
            before_value=event.before_value,
            after_value=event.after_value,
        )
        context = cls.build_context(
            event.mechanism_type,
            selected_motion_point_label=event.selected_motion_point,
            parameter_change=change,
        )
        return SensemakingContext(
            mechanism_type=context.mechanism_type,
            story=context.story,
            selected_motion_point_label=context.selected_motion_point_label,
            selected_motion_point_key=context.selected_motion_point_key,
            change=context.change,
            cause_line=context.cause_line,
            effect_line=context.effect_line,
            principle_line=context.principle_line,
            watch_line=context.watch_line,
            evidence_line=event.evidence_summary or context.evidence_line,
            build_check=context.build_check,
            teacher_prompt=context.teacher_prompt,
            point_snapshots=context.point_snapshots,
            confidence=context.confidence,
            evidence_pending=context.evidence_pending,
        )

    @staticmethod
    def describe_change(rule: CauseEffectRule, event: FoundrySensemakingEvent) -> str:
        """Build one concise change sentence for legacy callers."""
        return (
            f"{event.parameter_label}: {event.before_value} → {event.after_value}. "
            f"{rule.effect_label}"
        )

    @classmethod
    def _point_snapshots_for(
        cls,
        mechanism_type: str,
        current_positions: Mapping[str, object] | None,
        previous_positions: Mapping[str, object] | None,
    ) -> tuple[SensemakingPointSnapshot, ...]:
        if current_positions is None:
            return ()

        snapshots: list[SensemakingPointSnapshot] = []
        for point in cls._POINT_SPECS.get(mechanism_type, ()):
            snapshot = cls._snapshot_for_point(
                point.state_key,
                point.snapshot_label,
                current_positions,
                previous_positions,
            )
            if snapshot is not None:
                snapshots.append(snapshot)
        return tuple(snapshots)

    @classmethod
    def _snapshot_for_point(
        cls,
        key: str,
        label: str,
        current_positions: Mapping[str, object],
        previous_positions: Mapping[str, object] | None,
    ) -> SensemakingPointSnapshot | None:
        current = cls._finite_point_pair(current_positions.get(key))
        if current is None:
            return None
        previous = None
        if previous_positions is not None:
            previous = cls._finite_point_pair(previous_positions.get(key))
        previous_x = previous[0] if previous else None
        previous_y = previous[1] if previous else None
        return SensemakingPointSnapshot(
            key=key,
            label=label,
            x=current[0],
            y=current[1],
            previous_x=previous_x,
            previous_y=previous_y,
        )

    @classmethod
    def _watch_and_evidence_line(
        cls,
        mechanism_type: str,
        selected_point: SensemakingMotionPoint | None,
        selected_point_label: str,
        current_parameters: Mapping[str, object],
        snapshots: tuple[SensemakingPointSnapshot, ...],
        evidence_pending: bool = False,
    ) -> tuple[str, str]:
        if evidence_pending:
            return (
                f"Watch {selected_point_label} after the preview redraws.",
                "Preview geometry is updating; compare the refreshed trace next.",
            )

        if mechanism_type in {"gear_train", "gear_linkage"}:
            teeth1 = cls._positive_number(current_parameters.get("gear1_teeth"), 12.0)
            teeth2 = cls._positive_number(current_parameters.get("gear2_teeth"), 18.0)
            ratio = teeth1 / teeth2 if teeth2 else 0.0
            if mechanism_type == "gear_linkage":
                arm = cls._positive_number(current_parameters.get("linkage_arm_length"), 40.0)
                return (
                    "Watch the linkage pin/end: the driven gear now creates a crank motion.",
                    f"Ratio {teeth1:.0f}:{teeth2:.0f}; linkage arm length {arm:.0f} mm sets reach.",
                )
            return (
                "Watch the driven gear: speed changes, direction stays reversed.",
                f"Ratio {teeth1:.0f}:{teeth2:.0f}; output turns about {ratio:.2f}× per input turn.",
            )

        if mechanism_type == "planetary_gear":
            sun = cls._positive_number(current_parameters.get("sun_teeth"), 12.0)
            planet = cls._positive_number(current_parameters.get("planet_teeth"), 14.0)
            count = cls._positive_number(current_parameters.get("planet_count"), 1.0)
            return (
                "Watch the planet/output pin: the motion stays compact while the carrier orbits.",
                f"Sun {sun:.0f} teeth, planet {planet:.0f} teeth, {count:.0f} planets share the carrier.",
            )

        if mechanism_type == "slider_crank":
            crank = cls._positive_number(current_parameters.get("crank_length"), 80.0)
            rod = cls._positive_number(current_parameters.get("rod_length"), 140.0)
            return (
                "Watch the slider pin: it should move straight along the guide.",
                f"Estimated stroke ≈ {2.0 * crank:.0f} mm; rod length {rod:.0f} mm shapes smoothness.",
            )

        if not snapshots:
            return (
                f"Watch {selected_point_label} after the preview redraws.",
                "Preview evidence will refresh after this edit.",
            )

        selected_snapshot = None
        if selected_point is not None:
            selected_snapshot = next(
                (snapshot for snapshot in snapshots if snapshot.key == selected_point.state_key),
                None,
            )
        if selected_snapshot is None:
            selected_snapshot = snapshots[-1]

        snapshot_line = " / ".join(snapshot.summary for snapshot in snapshots)
        movement_line = cls._movement_line(selected_snapshot)
        evidence = f"{snapshot_line}. {movement_line}" if movement_line else snapshot_line
        return (f"Watch {selected_point_label}: compare its trace before and after.", evidence)

    @staticmethod
    def _movement_line(snapshot: SensemakingPointSnapshot) -> str:
        movement = snapshot.movement_mm
        if movement is None:
            return ""
        if movement < 0.5:
            return f"{snapshot.label} stayed almost in the same place."
        return f"{snapshot.label} moved about {movement:.0f} mm from the previous preview."

    @staticmethod
    def _finite_point_pair(value: object) -> tuple[float, float] | None:
        if not isinstance(value, list | tuple) or len(value) < 2:
            return None
        x = SensemakingService._finite_number(value[0], math.nan)
        y = SensemakingService._finite_number(value[1], math.nan)
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        return x, y

    @staticmethod
    def _finite_number(value: object, default: float) -> float:
        if isinstance(value, bool):
            return default
        try:
            result = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
        return result if math.isfinite(result) else default

    @classmethod
    def _positive_number(cls, value: object, default: float) -> float:
        result = cls._finite_number(value, default)
        return result if result > 0.0 else default

    @staticmethod
    def normalize_mechanism_type(mechanism_type: str) -> str:
        """Normalize mechanism aliases via the neutral Foundry type canonicalizer."""
        return canonical_mechanism_type(mechanism_type)

    @staticmethod
    def _normalize_mechanism_type(mechanism_type: str) -> str:
        return SensemakingService.normalize_mechanism_type(mechanism_type)
