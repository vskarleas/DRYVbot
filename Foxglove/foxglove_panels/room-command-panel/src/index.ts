import { ExtensionContext } from "@foxglove/extension";
import { initRoomCommandPanel } from "./RoomCommandPanel";

export function activate(extensionContext: ExtensionContext): void {
  extensionContext.registerPanel({
    name: "Room Command",
    initPanel: initRoomCommandPanel,
  });
}