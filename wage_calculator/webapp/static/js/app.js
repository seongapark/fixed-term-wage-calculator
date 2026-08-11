import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";
import { render as renderTargets } from "./targets.js";
import { render as renderResult } from "./result.js";
import { render as renderEvidence } from "./evidence.js";
import { openSettingsModal } from "./confirmModals.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);
registerRoute("targets", renderTargets);
registerRoute("result", renderResult);
registerRoute("evidence", renderEvidence);

document.getElementById("settings-btn").addEventListener("click", () => openSettingsModal());

navigate("upload");
