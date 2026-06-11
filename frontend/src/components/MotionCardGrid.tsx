import { motion, useReducedMotion, type Transition } from "framer-motion";
import type { ReactNode } from "react";

export function MotionCardGrid({
  children,
  className = "grid gap-4 sm:grid-cols-2 xl:grid-cols-6",
}: {
  children: ReactNode[];
  className?: string;
}) {
  const prefersReduced = useReducedMotion();
  const transition: Transition = prefersReduced ? { duration: 0 } : { duration: 0.3, ease: "easeOut" };

  return (
    <div className={className}>
      {children.map((child, index) => (
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          initial={{ opacity: 0, y: 5 }}
          key={index}
          transition={{ ...transition, delay: prefersReduced ? 0 : index * 0.025 }}
        >
          {child}
        </motion.div>
      ))}
    </div>
  );
}
