\section{The \papershort{} System}
\label{sec:system}

\begin{figure}[ht]
  \centering
  \includegraphics[width=1\linewidth]{figs/flow.png}
  \caption{\textbf{\papershort{} workflow from design to fabrication.}
  (A) Users sketch a rough motion path on the canvas.
  (B) The system smooths the path while preserving extremes.
  (C) Users adjust the path by repositioning vertices.
  (D) The system applies a selected four-bar linkage candidate to support the specified motion path.
  (E) Editing mechanism with a motion preview that shows linkage alignment.
  (F) The system exports fabrication-ready blueprints with labeled parts.
  (G) Physical parts fabricated from the blueprint (e.g., 3D-printed linkages).
  (H) Assembled automaton prototype demonstrating the leg-lifting motion. This pipeline also scaffolds the three stages detailed below (Stage 1: A–C; Stage 2: D-E; Stage 3: F-H).}
  \Description{Workflow from design to fabrication using the system. (A) A user sketches a rough motion path on a digital canvas. (B) The system smooths the path while retaining its extreme points. (C) The user refines the motion by repositioning vertices. (D) A candidate four-bar linkage is applied to approximate the motion path. (E) The mechanism is edited with a preview showing linkage alignment. (F) The system generates fabrication-ready blueprints with labeled parts. (G) Physical parts such as 3D-printed linkages are fabricated from the blueprints. (H) An assembled automaton prototype demonstrates the leg-lifting motion. The pipeline illustrates three stages: Stage 1 (A–C), Stage 2 (D–E), and Stage 3 (F–H).}
  \label{fig:system:flow}
\end{figure}

MotionSmith is a sketch-based computational design system for creating automata. The system combines direct on-canvas manipulation with solver-based reasoning, in which constraint solvers compute valid kinematics and mechanism configurations. Users can sketch and edit directly on a canvas over an uploaded image, while real-time simulation renders constraints and kinematics. MotionSmith is designed to support exploratory, tinkering-like workflows in which makers continually iterate on their ideas, revisiting earlier stages of design to test alternatives and pursue new possibilities. To ensure the outputs remain fabricable, the system proposes mechanism solutions that simplify construction by reducing part count and precision needs. The system also incorporates features that help interpret and scaffold makers’ creative intent, enabling articulation and refinement of ideas such as intended motion paths, expressive pacing, and fabricable mechanism constraints. \Cref{fig:system:flow} shows MotionSmith’s end-to-end pipeline from sketching a target motion (A–C) \tbfeat{1–3}, through mechanism synthesis and simulation (D, E) \tbfeat{4–6}, to fabrication-ready output (F) and assembly (G, H) \tbfeat{7}.

The system provides these key functionalities across three stages:

\begin{itemize}
\item \emph{Stage 1. Identifying a goal:} Users upload an image, configure the skeleton, and sketch a motion path to define the intended movement. (see \Cref{fig:system:flow}~A–C)
\item \emph{Stage 2. Generating supporting mechanism candidates:} The system generates three alternative mechanism designs, which users can simulate and refine through interactive editing. (see \Cref{fig:system:flow}~D–E)
\item \emph{Stage 3. Supporting fabrication:} The finalized design is converted into fabrication-ready blueprints that can be exported as SVG or PDF files. (see \Cref{fig:system:flow}~F-H)
\end{itemize}

While \Cref{fig:system:interface} illustrating interfaces, \Cref{tab:system-features} and \Cref{fig:system:staged} enumerate the key features by stage, coupling specific user actions with the forms of agency the system is designed to support.

\begin{figure}[ht]
    \centering
    \includegraphics[width=1\linewidth]{figs/interface.png}
    \caption{\textbf{\papershort{} interface.}
    (A) Main canvas for on-image authoring: users select a body part and draw a motion path; live simulation shows the traced trajectory and kinematic overlays (magnified inset).
    (B) Path drawing with smoothing: a slider toggles raw versus idealized curves while preserving extreme poses.
    (C) Parametric control (example: four-bar): bounded sliders expose ground/input/coupler/output lengths and anchors; edits are guard-aware (e.g., transmission angle, branch consistency).
    (D) Blueprint export: generates character/mechanism packets (SVG/PDF) with minimal dimensions for fabrication.
    (E) Mechanism candidates: a dialog presents ranked alternatives (four-bar, cam–follower, gears) with similarity scores; a chosen candidate is instantiated on the canvas for editing.
    (F) Animation control: play/stop, speed, and timing profile (e.g., linear/eased) for pacing review independent of geometry. Collectively, these panels foreground a tinkerable yet guard-aware workflow.}
    \Description{Interface of the system. (A) Main canvas for authoring on an image: the user selects a body part and draws a motion path, with live simulation showing the trajectory and kinematic overlays (magnified inset). (B) Path drawing with smoothing: a slider toggles between raw and idealized curves while preserving extreme poses. (C) Parametric control for mechanisms such as four-bar linkages: bounded sliders adjust ground, input, coupler, and output lengths as well as anchors, with edits constrained by guard-aware checks like transmission angle and branch consistency. (D) Blueprint export: generates character and mechanism packets (SVG/PDF) with minimal dimensions for fabrication. (E) Mechanism candidates: a dialog shows ranked alternatives (four-bar, cam–follower, gears) with similarity scores, and a chosen candidate is instantiated on the canvas for editing. (F) Animation control: play, stop, speed adjustment, and timing profiles (linear or eased) enable review of motion pacing independent of geometry. Together, these panels support a guard-aware and exploratory workflow.}
    \label{fig:system:interface}
\end{figure}

\subsection{Stage 1. Identifying a goal}
\label{sec:system:stage1}
In the first stage, the maker begins by creating an articulated 2D character and specifying a desirable animation as a motion curve, which serves as the goal for the subsequent stage.

The process starts with uploading a rasterized image of the character to be built~\feat{1}. Our system then proposes a human-like rig using a template-based pose-estimation initializer inspired by Animated Drawings~\cite{smith2023animated} and CharSegNet~\cite{srivastava2025childlikeshapes}. This initializer segments the drawing into named parts through a lightweight stroke–pixel graph seeded by joint locations, yielding editable part masks and attachment handles suitable for later anchoring and fabrication\ (\Cref{fig:system:authoring}A). The output is a set of named joints (e.g., \texttt{head}, \texttt{torso}, \texttt{L/R-arm-upper/lower}, and \texttt{L/R-leg-upper/lower}) and their $2$D positions, while following the pre-defined hierarchy of the template. While the default template assumes a human-like character, the maker may switch to alternative templates or define their own for non-human characters.

Once the articulated character is established, the maker specifies the desired motion of selected joints~\feat{2}. Users first indicate the target joint to be animated and then draw a motion curve as time-indexed keypoints $(t_i, \mathbf{x}_i)$ over the duration $0 \leq t_i \leq T$. As a result, the curve captures both positional movements and their velocity profiles. After the keypoints are defined, tolerance-based smoothing is applied while preserving extreme positions, followed by fitting Catmull–Rom splines for interpolation\ (\Cref{fig:system:authoring}B).

The system supports iterative refinement, allowing users to review visualizations of the motion (\Cref{fig:system:authoring}D), adjust keypoints, or modify parameterized features that influence smoothness and scale~\feat{3}. In some cases, a motion curve may fall outside the feasible range of the specified joint, making the motion mechanically infeasible. To address this, the system automatically snaps the curve to the nearest realizable trajectory while still displaying the original curve for reference\ (\Cref{fig:system:authoring}C). This iterative editing with automatic correction is designed to maintain user intent while increasing the feasibility of mechanism synthesis in the next stage.

\begin{figure}[ht]
  \centering
  \includegraphics[width=1\linewidth]{figs/system-authoring.png}
  \caption{\textbf{Authoring motion.}
  (A) The initializer proposes a skeleton with editable part masks over the character image.
  (B) Users draw motion paths, shown with a dual-track preview of raw (green) and max smoothed (purple) curves.
  (C) The system generates a mechanism aligned with the path and retargets motion to the nearest feasible pose while preserving the target curve.
  (D) Sampled poses illustrate pacing along the path, normalized to the chosen animation duration.}
  \Description{Four panels. A: a character with skeleton joints and editable part masks.
  B: two overlaid motion paths (green jagged vs. purple smoothed) drawn for the hand.
  C: A four-bar linkage is overlaid on the arm, showing retargeting while the target curve remains visible.
  D: the hand path annotated with multiple sample points indicating pacing along the motion.}
  \label{fig:system:authoring}
\end{figure}

\subsection{Stage 2. Generating and editing supporting mechanism candidates}
\label{sec:system:stage2}

After refining the motion path, the maker clicks the \emph{Get Mechanism} button in the left panel, prompting the system to generate three distinct mechanism candidates~\feat{4}. Our mechanism selection algorithm follows a template-based approach inspired by \citet{coros2013computational}, which combines mechanism selection from pre-generated designs followed by parameter refinement. \Cref{fig:system:mechanisms} illustrates the three families we surface to users (A–C) complementing the editable parameters and guardrails summarized in \Cref{tab:parameters}.

The system begins by retrieving promising mechanisms from the pre-generated database that can closely approximate the maker-specified motion curve. To ensure coverage, we populate candidates across three mechanism families: four-bar linkages, cam-followers, and spur/planetary gears.
% These mechanism types (\Cref{fig:system:mechanisms}) are instantiated not only as abstract kinematic templates but also as fabrication-ready exports (panels D–F).
Parameters are randomly sampled to span a wide range of motions, while infeasible designs are filtered out. The details of the parameters are illustrated in \Cref{tab:parameters}.

We pair perceptual-faithful curve matching with feasibility-aware refinement to produce edit-stable candidates before exposing them for tinkering. From this database, the system selects three top candidates, one from each family, by minimizing the normalized directed Hausdorff distance between the maker’s motion curve $\mathbf{x}_{1, \cdots, N}$ and the candidate curve $\mathbf{\hat{x}}_{1, \cdots, N}$. We resample time indices with the fixed timestep to match velocity profile. Each selected mechanism is then further refined through constrained optimization of the parameter $\theta$.
\begin{equation}
\min_{\theta}\; d_{\text{haus}}\!\big(\mathbf{x}_{1, \cdots, N}, \mathbf{\hat{x}}_{1, \cdots, N}(\theta)\big)
\quad\text{s.t.}\; c_m(\theta) > 0,\quad m=1,\cdots,M.
\end{equation}
While the primary objective is to minimize Hausdorff distance $d_{\text{haus}}$, the optimization also incorporates feasibility constraints $c_m$, such as ensuring minimal curvature exceeds a specified threshold for Cam-followers. The further details are described in \Cref{tab:parameters}. These constraints are expressed as soft penalties with L2 regularization and a weighting parameter $\lambda$, and the resulting objective is solved using the sampling-based CMA-ES algorithm~\cite{varelas2018comparative}.
% 하교수님 리뷰 필요 (2025-09-11)
After optimization, the system reports an accuracy score~\feat{4}, defined as
\[
\text{Acc} = 100 \cdot \Bigl(1 - \tfrac{d^\star_{\text{haus}}}{D_{\text{norm}}}\Bigr),
\]
where $d^\star_{\text{haus}}$ is the Hausdorff distance after alignment between the user path and a candidate trajectory, and $D_{\text{norm}}$ is a shape-intrinsic normalizer, where we use the path’s bounding box diagonal. These scores are presented as ``Match \%'' in the interface (\Cref{fig:system:interface}E).

Once the initial candidate is selected, the maker may continue to edit the trajectory (Stage 1) or mechanism parameters directly (Stage 2) on the canvas~\feat{5}. Each edit triggers a re-execution of the constrained optimization with a warm start, allowing the system to refine the candidate mechanism while preserving feasibility~\feat{6}. This process enables the maker to iteratively explore, verify, and adjust their design within the system and ensures that mechanism synthesis and creative intent remain coupled throughout the workflow.


\begin{figure}
    \centering
    \includegraphics[width=1\linewidth]{figs/mechanisms.png}
    \caption{\textbf{Mechanism families in \papershort{}.}
    (A) Four-bar linkage generated from a user-drawn path.
    (B) Cam–follower configuration mapping motion to rotation.
    (C) Gear pair in motion, showing driver and follower gears.
    }
    \Description{Mechanism families supported by the system. (A) A four-bar linkage generated from a user-drawn motion path. (B) A cam–follower configuration that maps linear motion into rotational output. (C) A pair of gears in motion, showing the interaction between a driver gear and a follower gear.}
    \label{fig:system:mechanisms}
\end{figure}

\renewcommand{\arraystretch}{1.2}
\begin{table}
\centering
\begin{tabularx}{\textwidth}{L{2.8cm} Y Y L{3.6cm}}
    \toprule
    \textbf{Family} & \textbf{Editable Parameters} & \textbf{Invariants} & \textbf{Constraints} \\
    \midrule
    Four-bar linkage &
    Ground placement \newline Moving pivot locations \newline Bar lengths &
    Joint types \newline Planar assembly &
    Branch consistency \newline Transmission angle band \newline Non-degenerate lengths \\
    \midrule
    Cam–follower &
    Lift/dwell control points \newline Follower tip type &
    Guided follower \newline Layer planarity &
    Curvature minima \\
    \midrule
    Spur/Planetary gears &
    Module \newline Tooth count(s) \newline Center distances &
    Pressure-angle range \newline Integer teeth &
    Module/center-distance compatibility \\
    \bottomrule
\end{tabularx}
\caption{\textbf{Mechanism parameters.}
For each family, we list:
\emph{Editable parameters}, which expose user-facing degrees of freedom for interactive tinkering;
\emph{Invariants}, which remain fixed by definition of the mechanism type and enforce consistency during solver-based editing; and
\emph{Constraints}, which are automatically checked to ensure mechanical feasibility (e.g., branch consistency and transmission angle limits for linkages, curvature bounds for cam profiles, and compatibility between module and center distance for gears).
These constraints act as guardrails that maintain fabricability while still affording creative flexibility in parameter exploration.}
\label{tab:parameters}
\end{table}

\subsection{Stage 3. Supporting fabrication}
\label{sec:system:stage3}
As the final stage of the workflow, the system enables the maker to generate a fabrication-ready blueprint of the design~\feat{7}. To support verification before fabrication, the system provides multiple views such as orthographic projections for dimension accuracy, isometric perspectives for overall form, and exploded or sectional views that reveal internal assemblies. These views allow the maker to inspect alignment, fit, and assembly feasibility before committing to fabrication. Panels G–I in \Cref{fig:system:staged} and depict the exported packets and their translation to partial and final assemblies.

The resulting blueprint is exported as an SVG or PDF file~\feat{7}, ready for use with digital fabrication tools. To ensure persistence and precise export, projects are saved as JSON with explicit units. At export time, the system generates two distinct vector packets: a character packet that contains silhouette layers and attachment holes, and a mechanism packet that contains layered drawings with a minimal dimension set as well as optional isometric or exploded inserts. Fabrication-specific parameters such as kerf width, spacing, and minimum size thresholds are initialized with empirical defaults derived from prior builds, and makers can adjust these parameters at export time to match their fabrication context. Together with panels E–H in \Cref{fig:system:flow}, these views substantiate the ‘fabricatable by design’ claim that anchors our system goals.


\begin{table}[p]
\begin{tabularx}{\textwidth}{L{3.4cm} Y Y}
\toprule
    \textbf{System feature} & \textbf{User interaction} & \textbf{Intended support for agency} \\

    \bottomrule
    \stagerow{Stage 1: Identifying a goal}
    \midrule
    \feat{1}{init} Initialization &
    Upload an image; generates a skeleton with editable parts and handles. &
    Quickly set up an articulated character while retaining flexibility for changes. \\
    \feat{2}{motion} Motion path&
    Draw or edit a curve for a target joint; adjust keypoints or use smoothing slider. &
    Externalize intended motion in a sketchable form that can be refined iteratively. \\
    \feat{3}{sim} Simulation/pacing&
    Play back motion with live preview; adjust speed and select linear/eased timing. &
    Review expressive pacing independently of geometry and explore variations. \\

    \bottomrule
    \stagerow{Stage 2: Mechanism exploration}
    \midrule
    \feat{4}{candidate} Candidate generation&
    Click \emph{Get Mechanism} to see three families (four-bar, cam–follower, gears). &
    Compare different feasible realizations of the same intent before committing. \\
    \feat{5}{editing} On-canvas editing&
    Adjust anchors, pivots, or lengths through bounded sliders with guards. &
    Safely tinker with mechanism parameters while solver maintains feasibility. \\
    \feat{6}{diagnostics} Diagnostics &
    Visual overlays show infeasible poses, conflicts, and unreachable segments. &
    Prevent hidden errors and support a “learn by doing” style of tinkering. \\

    \bottomrule
    \stagerow{Stage 3: Fabrication support}
    \midrule
    \feat{7}{blueprint}  Blueprint export &
    Generate fabrication-ready outputs as SVG/PDF with bill of materials included. &
    Bridge digital design to tangible automata with fabrication-safe exports. \\
\bottomrule
\end{tabularx}
\caption{Key features of \papershort{} organized across the three workflow stages.
Stage~1 establishes the design goal by initializing a rig and sketching desired motion paths.
Stage~2 supports exploration and refinement through system-generated mechanism candidates, interactive parameter editing, and visual diagnostics.
Stage~3 bridges digital and physical domains by exporting fabrication-ready blueprints, ensuring that exploratory designs remain realizable as tangible automata.}
\Description{Key system features organized across three workflow stages. Stage 1, “Identifying a goal,” includes initialization by uploading an image to generate an editable skeleton, sketching and refining motion paths, and simulating pacing through live preview and adjustable timing. Stage 2, “Mechanism exploration,” provides candidate generation from three mechanism families, interactive on-canvas editing of anchors and lengths with guardrails, and diagnostic overlays to highlight infeasible or conflicting poses. Stage 3, “Fabrication support,” enables blueprint export as fabrication-ready SVG/PDF files with a bill of materials, bridging digital designs to physical automata.}
\label{tab:system-features}
\end{table}

\begin{figure}[p]
    \centering
    \includegraphics[width=1\linewidth]{figs/04-system-staged-matching.png}
    \caption{\textbf{System features of \papershort{}.} Panels (A–G) illustrate the features listed in \Cref{tab:system-features}; panels (H–I) depict fabrication outcomes: partial assembly (H) and the final prototype demonstrating the intended motion (I).}
    \Description{System features demonstrated across stages. Panels (A–C) show Stage 1: initialization with a generated skeleton, motion path sketching, and pacing simulation. Panels (D–F) show Stage 2: candidate mechanism generation, on-canvas editing, and diagnostic overlays. Panel (G) shows Stage 3: blueprint export with fabrication dimensions. Panels (H–I) illustrate fabrication outcomes, including partial assembly of mechanism parts and a final prototype demonstrating the intended motion.}
    \label{fig:system:staged}
\end{figure}


%===============================
% Implementation Deatils
%===============================

\subsection{Implementation Details}
\label{system:implementation}

\papershort{} is implemented as a cross-platform desktop application for macOS and Windows. The interface is implemented with \texttt{PyQt6}, while real-time rendering uses \texttt{QtQuick}/OpenGL. A C++/Python core, exposed through \texttt{pybind11}, provides geometry and kinematics utilities, mechanism search, and feasibility checks. All inference and simulation run locally, maintaining interactive performance at 60 FPS on laptops.
