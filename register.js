// Player Registration & UPI Payment Handling
let capturedPhotoBlob = null;
let webcamStream = null;

// Tournament config passed from template
const config = window.TOURNAMENT_CONFIG || {
  upi_id: 'saidapur.cricket@upi',
  payee_name: 'Saidapur Premier League',
  registration_fee: 200
};

document.addEventListener('DOMContentLoaded', () => {
  initPhotoHandling();
  initUPIPayments();
  initFormSubmission();
});

function initPhotoHandling() {
  const fileInput = document.getElementById('photoFileInput');
  const cameraInput = document.getElementById('photoCameraInput');
  const previewImg = document.getElementById('photoPreview');
  const webcamModal = document.getElementById('webcamModal');
  const webcamVideo = document.getElementById('webcamVideo');

  // Trigger file picker
  document.getElementById('btnUploadFile')?.addEventListener('click', () => {
    fileInput.click();
  });

  // Mobile camera capture trigger
  document.getElementById('btnCameraMobile')?.addEventListener('click', () => {
    // If mobile or has camera input
    if (cameraInput) {
      cameraInput.click();
    }
  });

  // Desktop webcam modal trigger
  document.getElementById('btnWebcamDesktop')?.addEventListener('click', async () => {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        webcamStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } });
        webcamVideo.srcObject = webcamStream;
        webcamVideo.play();
        webcamModal.style.display = 'flex';
      } catch (err) {
        alert('Could not access camera: ' + err.message + '. Please use the Upload File button.');
      }
    } else {
      alert('Camera access is not supported by your browser. Please upload a photo.');
    }
  });

  // Capture snapshot from webcam
  document.getElementById('btnCaptureSnapshot')?.addEventListener('click', () => {
    const canvas = document.createElement('canvas');
    canvas.width = webcamVideo.videoWidth || 480;
    canvas.height = webcamVideo.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(webcamVideo, 0, 0, canvas.width, canvas.height);
    
    canvas.toBlob((blob) => {
      capturedPhotoBlob = blob;
      previewImg.src = URL.createObjectURL(blob);
      closeWebcam();
    }, 'image/jpeg', 0.9);
  });

  document.getElementById('btnCloseWebcam')?.addEventListener('click', closeWebcam);

  function closeWebcam() {
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      webcamStream = null;
    }
    webcamModal.style.display = 'none';
  }

  // Handle file uploads (both file picker & mobile capture)
  function handleFileSelected(e) {
    const file = e.target.files[0];
    if (file) {
      capturedPhotoBlob = file;
      const reader = new FileReader();
      reader.onload = (evt) => {
        previewImg.src = evt.target.result;
      };
      reader.readAsDataURL(file);
    }
  }

  fileInput?.addEventListener('change', handleFileSelected);
  cameraInput?.addEventListener('change', handleFileSelected);
}

function initUPIPayments() {
  const nameInput = document.getElementById('playerName');
  const qrImg = document.getElementById('upiQrCode');
  const upiIdDisplay = document.getElementById('upiIdDisplay');
  const feeDisplay = document.getElementById('feeAmountDisplay');
  
  if (feeDisplay) feeDisplay.textContent = '₹' + config.registration_fee;
  if (upiIdDisplay) upiIdDisplay.textContent = config.upi_id;

  function updateUPIUrls() {
    const playerName = (nameInput?.value.trim()) || 'Player';
    const note = encodeURIComponent(`KPL Fee - ${playerName}`);
    const upiUri = `upi://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;
    
    // Update QR Code
    if (qrImg) {
      qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(upiUri)}`;
    }

    // Update Deep-Link buttons
    const btnPhonePe = document.getElementById('btnPayPhonePe');
    const btnGPay = document.getElementById('btnPayGPay');
    const btnPaytm = document.getElementById('btnPayPaytm');
    const btnBhim = document.getElementById('btnPayBhim');

    if (btnPhonePe) btnPhonePe.href = `phonepe://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;
    if (btnGPay) btnGPay.href = `gpay://upi/pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;
    if (btnPaytm) btnPaytm.href = `paytmmp://pay?pa=${config.upi_id}&pn=${encodeURIComponent(config.payee_name)}&am=${config.registration_fee}&cu=INR&tn=${note}`;
    if (btnBhim) btnBhim.href = upiUri;
  }

  nameInput?.addEventListener('input', updateUPIUrls);
  updateUPIUrls();

  // Copy UPI ID button
  document.getElementById('btnCopyUpi')?.addEventListener('click', () => {
    navigator.clipboard.writeText(config.upi_id);
    const copyBtn = document.getElementById('btnCopyUpi');
    copyBtn.textContent = '✓ Copied!';
    setTimeout(() => { copyBtn.textContent = 'Copy UPI ID'; }, 2000);
  });
}

function initFormSubmission() {
  const form = document.getElementById('registrationForm');
  const submitBtn = document.getElementById('btnSubmitReg');
  const alertBox = document.getElementById('formAlert');

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    alertBox.style.display = 'none';

    const name = document.getElementById('playerName').value.trim();
    const phone = document.getElementById('playerPhone').value.trim();
    const roleRadio = document.querySelector('input[name="playerRole"]:checked');
    const batting = document.getElementById('battingStyle').value;
    const bowling = document.getElementById('bowlingStyle').value;
    const paymentMethod = document.getElementById('paymentMethod').value;
    const utr = document.getElementById('transactionId').value.trim();
    const paymentProofFile = document.getElementById('paymentScreenshot')?.files[0];

    if (!name) return showAlert('Please enter player name.');
    if (!phone || phone.length < 10) return showAlert('Please enter a valid 10-digit mobile number.');
    if (!roleRadio) return showAlert('Please select player role (Batsman, Bowler, All-Rounder, Wicket Keeper).');
    // UTR is optional

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Submitting Registration...';

    const formData = new FormData();
    formData.append('name', name);
    formData.append('phone', phone);
    formData.append('role', roleRadio.value);
    formData.append('batting_style', batting);
    formData.append('bowling_style', bowling);
    formData.append('payment_method', paymentMethod);
    formData.append('transaction_id', utr);
    formData.append('reg_amount', config.registration_fee);

    if (capturedPhotoBlob) {
      formData.append('photo', capturedPhotoBlob, 'player_photo.jpg');
    }
    if (paymentProofFile) {
      formData.append('screenshot', paymentProofFile);
    }

    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        window.location.href = `/register/success/${encodeURIComponent(data.player_id)}`;
      } else {
        showAlert(data.message || 'Error saving registration.');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Complete Registration & Pay';
      }
    } catch (err) {
      showAlert('Network error: ' + err.message);
      submitBtn.disabled = false;
      submitBtn.textContent = 'Complete Registration & Pay';
    }
  });

  function showAlert(msg) {
    if (alertBox) {
      alertBox.textContent = msg;
      alertBox.style.display = 'block';
      alertBox.scrollIntoView({ behavior: 'smooth' });
    } else {
      alert(msg);
    }
  }
}
