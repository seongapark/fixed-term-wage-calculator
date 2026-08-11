import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";
import { render as renderSpecialLeave } from "./specialLeave.js";

registerRoute("upload", renderUpload);
registerRoute("specialLeave", renderSpecialLeave);

navigate("upload");
