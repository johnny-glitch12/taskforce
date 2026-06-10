import { useEffect } from "react";

const BASE_TITLE = "Task Force — Build, Deploy & Monetize AI Agents";

/**
 * Sets document.title for a page, restoring the base title on unmount.
 * Usage: usePageTitle("Pricing") → "Pricing — Task Force"
 */
export default function usePageTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} — Task Force` : BASE_TITLE;
    return () => {
      document.title = BASE_TITLE;
    };
  }, [title]);
}
