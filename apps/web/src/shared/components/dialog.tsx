import { cn } from "@shared/utils/cn";
import { X } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";
import { useEffect } from "react";

type DialogProps = {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Width (e.g. "540px"). Default 540. */
  width?: string;
};

/** Modal overlay primitive. Click scrim or press Escape to close.
 *
 * No transitions / animations yet — POC keeps it lean. If we ever want a fade
 * in, add `transition-opacity duration-150` plus a deferred-mount pattern.
 */
export function Dialog({ open, onClose, children, width = "540px" }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <>
      <button
        type="button"
        aria-label="Close dialog"
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px] cursor-default"
        onClick={onClose}
      />
      <div
        // biome-ignore lint/a11y/useSemanticElements: native <dialog> requires
        // imperative .showModal() and doesn't compose with our render flow.
        role="dialog"
        aria-modal="true"
        className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 bg-surface border border-border-soft rounded-card shadow-lg max-h-[90vh] overflow-hidden flex flex-col"
        style={{ width }}
      >
        {children}
      </div>
    </>
  );
}

export function DialogHeader({
  className,
  children,
  onClose,
  ...props
}: HTMLAttributes<HTMLDivElement> & { onClose?: () => void }) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-border-soft px-4 py-3 flex-none",
        className,
      )}
      {...props}
    >
      <div className="flex-1 flex items-center gap-3 min-w-0">{children}</div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="text-text-3 hover:text-text-2"
          aria-label="Close"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}

export function DialogBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-4 py-3 overflow-y-auto flex-1", className)} {...props} />;
}

export function DialogFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 justify-end border-t border-border-soft px-4 py-3 flex-none",
        className,
      )}
      {...props}
    />
  );
}
