import { useRef, useState } from "react";

// Reconnecting the desktop must not overwrite the prompt someone is typing.
// An explicit native Save & Apply may replace it using force: true.
export function useHostPrompt() {
  const [prompt, updatePrompt] = useState("");
  const edited = useRef(false);
  const setPrompt = value => { edited.current = true; updatePrompt(value); };
  const applyHostPrompt = (value, force = false) => {
    if (edited.current && !force) return false;
    if (force) edited.current = false;
    updatePrompt(value);
    return true;
  };
  return { prompt, setPrompt, applyHostPrompt, canRunHostAnalysis: force => force === true || !edited.current };
}
