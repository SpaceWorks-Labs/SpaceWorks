import { useState } from "react";
import { Avatar } from "./Avatar";

type ImageThumbnailProps = {
  src?: string | null;
  alt: string;
  className?: string;
};

export function ImageThumbnail({ src, alt, className = "h-12 w-12" }: ImageThumbnailProps) {
  const [failedSrc, setFailedSrc] = useState<string>();
  return (
    <div className={`${className} shrink-0 overflow-hidden rounded-md border border-line bg-surface [&>span]:h-full [&>span]:w-full [&>span]:rounded-none [&>span]:border-0`}>
      {src && failedSrc !== src ? (
        <img src={src} alt={alt} className="h-full w-full object-cover" onError={() => setFailedSrc(src)} />
      ) : (
        <Avatar name={alt || "Equipment"} tone="accent" />
      )}
    </div>
  );
}
