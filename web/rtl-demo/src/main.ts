import "./styles.css";
import { start } from "./workspace";
import { el, button, errorText } from "./dom";
void start().catch((e) => {
  document.querySelector("#app")!.replaceChildren(
    el("div", "loading", errorText(e)),
    button("重新加载", () => location.reload()),
  );
});
