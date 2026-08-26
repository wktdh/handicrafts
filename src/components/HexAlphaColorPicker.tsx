import { HexAlphaColorPicker as ColorPicker } from "react-colorful";

export default function HexAlphaColorPicker({
  color,
  onChange,
}: {
  color: string;
  onChange: (color: string) => void;
}) {
  return <ColorPicker color={color} onChange={onChange} />;
}
