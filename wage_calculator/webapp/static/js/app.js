import { registerRoute, navigate } from "./router.js";
import { render as renderUpload } from "./upload.js";

registerRoute("upload", renderUpload);

navigate("upload");
