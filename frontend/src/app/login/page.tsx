"use client";

import { useState, useRef, useEffect, FormEvent, KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { Loader2, AlertCircle, Lock, Mail, ArrowRight, RotateCcw } from "lucide-react";
import api from "@/lib/api";

type LoginStage = "credentials" | "otp";

interface LoginError {
  message: string;
  type: "error" | "warning";
}

export default function LoginPage() {
  const router = useRouter();
  const [stage, setStage] = useState<LoginStage>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState<string[]>(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<LoginError | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [resendEnabled, setResendEnabled] = useState(false);

  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  useEffect(() => {
    if (countdown <= 0) {
      setResendEnabled(true);
      return;
    }
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  const formatCountdown = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const handleLoginSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await api.post("/auth/login", { email, password });
      const data = response.data;

      if (data.requires_otp) {
        setStage("otp");
        setCountdown(data.otp_expires_in || 600);
        setResendEnabled(false);
        setTimeout(() => otpRefs.current[0]?.focus(), 100);
      }
    } catch (err: any) {
      const status = err.response?.status;
      const message = err.response?.data?.detail || "An error occurred";

      if (status === 423) {
        setError({ message: "Account locked. Please try again later.", type: "error" });
      } else if (status === 401) {
        setError({ message: "Invalid email or password.", type: "error" });
      } else {
        setError({ message, type: "error" });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value.slice(-1);
    setOtp(newOtp);

    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }

    if (newOtp.every((d) => d !== "") && newOtp.join("").length === 6) {
      submitOtp(newOtp.join(""));
    }
  };

  const handleOtpKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      const newOtp = pasted.split("");
      setOtp(newOtp);
      otpRefs.current[5]?.focus();
      submitOtp(pasted);
    }
  };

  const submitOtp = async (code: string) => {
    setError(null);
    setLoading(true);

    try {
      await api.post("/auth/verify-otp", { email, otp: code });
      router.push("/dashboard");
    } catch (err: any) {
      const status = err.response?.status;
      const message = err.response?.data?.detail || "Verification failed";

      if (status === 410) {
        setError({ message: "OTP has expired. Please request a new one.", type: "warning" });
      } else if (status === 401) {
        setError({ message: "Invalid OTP. Please try again.", type: "error" });
      } else {
        setError({ message, type: "error" });
      }

      setOtp(["", "", "", "", "", ""]);
      otpRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setError(null);
    setResendEnabled(false);

    try {
      const response = await api.post("/auth/login", { email, password });
      setCountdown(response.data.otp_expires_in || 600);
      setOtp(["", "", "", "", "", ""]);
      otpRefs.current[0]?.focus();
    } catch {
      setError({ message: "Failed to resend OTP. Please try again.", type: "error" });
      setResendEnabled(true);
    }
  };

  return (
    <div className="min-h-screen bg-bezalel-bg flex items-center justify-center p-4">
      {/* Background gradient effect */}
      <div className="fixed inset-0 bg-gradient-to-br from-bezalel-highlight/5 via-transparent to-transparent pointer-events-none" />

      <div className="relative w-full max-w-md animate-fade-in">
        {/* Branding */}
        <div className="text-center mb-10">
          <h1 className="text-5xl font-extralight tracking-[0.2em] text-bezalel-text mb-2">
            Bezalel
            <span className="text-bezalel-highlight font-light">.AI</span>
          </h1>
          <div className="w-16 h-px bg-bezalel-highlight/40 mx-auto mt-4" />
        </div>

        {/* Card */}
        <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-8 shadow-2xl shadow-black/40">
          {stage === "credentials" ? (
            <form onSubmit={handleLoginSubmit} className="space-y-6">
              <div>
                <label className="block text-sm text-bezalel-text-secondary mb-2 uppercase tracking-wider">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bezalel-text-secondary" />
                  <input
                    ref={emailRef}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-bezalel-accent border border-bezalel-border rounded-lg pl-10 pr-4 py-3 text-bezalel-text placeholder-bezalel-text-secondary/50 focus:border-bezalel-highlight"
                    placeholder="you@example.com"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-bezalel-text-secondary mb-2 uppercase tracking-wider">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bezalel-text-secondary" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-bezalel-accent border border-bezalel-border rounded-lg pl-10 pr-4 py-3 text-bezalel-text placeholder-bezalel-text-secondary/50 focus:border-bezalel-highlight"
                    placeholder="Enter your password"
                    required
                    disabled={loading}
                  />
                </div>
              </div>

              {error && (
                <div
                  className={`flex items-center gap-2 p-3 rounded-lg text-sm animate-fade-in ${
                    error.type === "error"
                      ? "bg-red-500/10 border border-red-500/20 text-red-400"
                      : "bg-yellow-500/10 border border-yellow-500/20 text-yellow-400"
                  }`}
                >
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {error.message}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-bezalel-highlight hover:bg-bezalel-highlight/90 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 group"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    Sign In
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>
          ) : (
            <div className="space-y-6 animate-fade-in">
              <div className="text-center">
                <h2 className="text-lg font-medium text-bezalel-text mb-1">Verification Required</h2>
                <p className="text-sm text-bezalel-text-secondary">
                  Enter the 6-digit code sent to{" "}
                  <span className="text-bezalel-text">{email}</span>
                </p>
              </div>

              {/* OTP Inputs */}
              <div className="flex justify-center gap-3" onPaste={handleOtpPaste}>
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => {
                      otpRefs.current[index] = el;
                    }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(index, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(index, e)}
                    disabled={loading}
                    className="w-12 h-14 bg-bezalel-accent border border-bezalel-border rounded-lg text-center text-xl font-mono text-bezalel-text focus:border-bezalel-highlight disabled:opacity-50"
                  />
                ))}
              </div>

              {/* Countdown */}
              <div className="text-center">
                {countdown > 0 ? (
                  <p className="text-sm text-bezalel-text-secondary">
                    Code expires in{" "}
                    <span className="text-bezalel-text font-mono">{formatCountdown(countdown)}</span>
                  </p>
                ) : (
                  <p className="text-sm text-red-400">Code has expired</p>
                )}
              </div>

              {error && (
                <div
                  className={`flex items-center gap-2 p-3 rounded-lg text-sm animate-fade-in ${
                    error.type === "error"
                      ? "bg-red-500/10 border border-red-500/20 text-red-400"
                      : "bg-yellow-500/10 border border-yellow-500/20 text-yellow-400"
                  }`}
                >
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {error.message}
                </div>
              )}

              {/* Resend */}
              <div className="flex items-center justify-between">
                <button
                  onClick={() => {
                    setStage("credentials");
                    setError(null);
                  }}
                  className="text-sm text-bezalel-text-secondary hover:text-bezalel-text"
                >
                  Back to login
                </button>
                <button
                  onClick={handleResendOtp}
                  disabled={!resendEnabled}
                  className="flex items-center gap-1 text-sm text-bezalel-highlight hover:text-bezalel-highlight/80 disabled:text-bezalel-text-secondary disabled:cursor-not-allowed"
                >
                  <RotateCcw className="w-3 h-3" />
                  Resend Code
                </button>
              </div>

              {loading && (
                <div className="flex justify-center">
                  <Loader2 className="w-6 h-6 animate-spin text-bezalel-highlight" />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-bezalel-text-secondary/50 mt-8">
          Secure Access Only
        </p>
      </div>
    </div>
  );
}
