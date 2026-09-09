import Image from "next/image";

type Props = {
  className?: string;
  size?: number;
  priority?: boolean;
};

export default function HummingbirdMark({ className = "", size = 40, priority = false }: Props) {
  return (
    <Image
      src="/hummingbird-mark.png"
      alt=""
      width={size}
      height={size}
      priority={priority}
      className={`inline-block shrink-0 object-contain ${className}`}
      aria-hidden
    />
  );
}
