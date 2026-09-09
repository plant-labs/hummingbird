import AppMenu from "@/components/AppMenu";
import ModerationQueue from "@/components/ModerationQueue";

export default function ModerationPage() {
  return (
    <div className="relative">
      <div className="absolute left-5 top-5 z-40 md:left-8 md:top-7">
        <AppMenu />
      </div>
      <ModerationQueue />
    </div>
  );
}
