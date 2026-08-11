import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";
import { render as renderTargets } from "./targets.js";
import { openSettingsModal } from "./confirmModals.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);
registerRoute("targets", renderTargets);

document.getElementById("settings-btn").addEventListener("click", () => openSettingsModal());

navigate("upload");
