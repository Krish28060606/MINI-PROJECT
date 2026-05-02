let emailVerified = false;
let verifiedEmail = "";

function showPanel(type) {
  document.querySelectorAll(".tab").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(panel => panel.classList.remove("active"));

  if (type === "login") {
    document.querySelector(".tab:nth-child(1)").classList.add("active");
    document.getElementById("loginPanel").classList.add("active");
  } else {
    document.querySelector(".tab:nth-child(2)").classList.add("active");
    document.getElementById("signupPanel").classList.add("active");
  }
}

function setMessage(id, message, type) {
  const box = document.getElementById(id);
  box.className = "message " + type;
  box.textContent = message;
}

function clearMessage(id) {
  const box = document.getElementById(id);
  box.className = "message";
  box.textContent = "";
}

function togglePassword(inputId, button) {
  const input = document.getElementById(inputId);
  if (input.type === "password") {
    input.type = "text";
    button.textContent = "Hide";
  } else {
    input.type = "password";
    button.textContent = "Show";
  }
}

function setLoading(buttonId, isLoading, text) {
  const btn = document.getElementById(buttonId);
  if (!btn) return;

  if (isLoading) {
    btn.dataset.oldText = btn.textContent;
    btn.textContent = text || "Please wait...";
    btn.classList.add("loading");
    btn.disabled = true;
  } else {
    btn.textContent = btn.dataset.oldText || btn.textContent;
    btn.classList.remove("loading");
    btn.disabled = false;
  }
}

function updateStrength() {
  const password = document.getElementById("signupPassword").value;
  const bar = document.getElementById("strengthBar");
  let score = 0;

  if (password.length >= 6) score += 25;
  if (password.length >= 10) score += 25;
  if (/[A-Z]/.test(password)) score += 15;
  if (/[0-9]/.test(password)) score += 15;
  if (/[^A-Za-z0-9]/.test(password)) score += 20;

  bar.style.width = Math.min(score, 100) + "%";
}

function resetVerificationState() {
  emailVerified = false;
  verifiedEmail = "";
  document.getElementById("verifiedBadge").classList.remove("show");
}

async function sendEmailOtp() {
  clearMessage("signupMessage");

  const email = document.getElementById("signupEmail").value.trim().toLowerCase();

  if (!email) {
    setMessage("signupMessage", "Enter email first.", "error");
    return;
  }

  resetVerificationState();
  setLoading("sendOtpBtn", true, "Sending OTP...");

  try {
    const res = await fetch("/send-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email })
    });

    const data = await res.json();

    if (data.status === "success") {
      document.getElementById("otpArea").style.display = "block";
      setMessage("signupMessage", data.message || "OTP sent successfully.", "success");
    } else {
      setMessage("signupMessage", data.message || "OTP failed.", "error");
    }
  } catch (error) {
    setMessage("signupMessage", "Server error while sending OTP.", "error");
  } finally {
    setLoading("sendOtpBtn", false);
  }
}

async function verifyEmailOtp() {
  clearMessage("signupMessage");

  const email = document.getElementById("signupEmail").value.trim().toLowerCase();
  const otp = document.getElementById("signupOtp").value.trim();

  if (!otp) {
    setMessage("signupMessage", "Enter OTP first.", "error");
    return;
  }

  setLoading("verifyOtpBtn", true, "Verifying...");

  try {
    const res = await fetch("/verify-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, otp: otp })
    });

    const data = await res.json();

    if (data.status === "success") {
      emailVerified = true;
      verifiedEmail = email;
      document.getElementById("verifiedBadge").classList.add("show");
      setMessage("signupMessage", data.message || "Email verified.", "success");
    } else {
      setMessage("signupMessage", data.message || "OTP verification failed.", "error");
    }
  } catch (error) {
    setMessage("signupMessage", "Server error while verifying OTP.", "error");
  } finally {
    setLoading("verifyOtpBtn", false);
  }
}

async function createAccount() {
  clearMessage("signupMessage");

  const username = document.getElementById("signupUsername").value.trim();
  const email = document.getElementById("signupEmail").value.trim().toLowerCase();
  const phone = document.getElementById("signupPhone").value.trim();
  const password = document.getElementById("signupPassword").value;
  const confirmPassword = document.getElementById("signupConfirmPassword").value;

  if (!emailVerified || verifiedEmail !== email) {
    setMessage("signupMessage", "Please verify email OTP first.", "error");
    return;
  }

  if (!username || !email || !password || !confirmPassword) {
    setMessage("signupMessage", "Fill username, email, password and recheck password.", "error");
    return;
  }

  if (password !== confirmPassword) {
    setMessage("signupMessage", "Password and recheck password do not match.", "error");
    return;
  }

  setLoading("createAccountBtn", true, "Creating account...");

  try {
    const res = await fetch("/complete-signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username,
        email: email,
        phone: phone,
        password: password,
        confirm_password: confirmPassword
      })
    });

    const data = await res.json();

    if (data.status === "success") {
      setMessage("signupMessage", data.message || "Account created successfully.", "success");

      setTimeout(() => {
        showPanel("login");
        document.getElementById("loginId").value = username;
      }, 900);
    } else {
      setMessage("signupMessage", data.message || "Signup failed.", "error");
    }
  } catch (error) {
    setMessage("signupMessage", "Server error while creating account.", "error");
  } finally {
    setLoading("createAccountBtn", false);
  }
}

async function loginUser() {
  clearMessage("loginMessage");

  const loginId = document.getElementById("loginId").value.trim();
  const password = document.getElementById("loginPassword").value;

  if (!loginId || !password) {
    setMessage("loginMessage", "Enter username/email and password.", "error");
    return;
  }

  setLoading("loginBtn", true, "Logging in...");

  try {
    const res = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        login_id: loginId,
        password: password
      })
    });

    const data = await res.json();

    if (data.status === "success") {
      setMessage("loginMessage", "Login successful. Redirecting...", "success");
      setTimeout(() => {
        window.location.href = "/index";
      }, 650);
    } else {
      setMessage("loginMessage", data.message || "Login failed.", "error");
    }
  } catch (error) {
    setMessage("loginMessage", "Server error during login.", "error");
  } finally {
    setLoading("loginBtn", false);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const emailInput = document.getElementById("signupEmail");
  if (emailInput) {
    emailInput.addEventListener("input", resetVerificationState);
  }

  const authParams = new URLSearchParams(window.location.search);
  const authMode = authParams.get("mode");
  if (authMode === "signup") {
    showPanel("signup");
  } else {
    showPanel("login");
  }
});
