"use client";

import { useState, useEffect } from "react";
import { format } from "date-fns";

export default function Clock() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="text-center py-8">
      <div className="text-6xl font-extralight tracking-[0.1em] text-bezalel-text font-mono tabular-nums">
        {format(now, "HH:mm:ss")}
      </div>
      <div className="text-lg text-bezalel-text-secondary mt-2 font-light">
        {format(now, "EEEE, MMMM d, yyyy")}
      </div>
    </div>
  );
}
