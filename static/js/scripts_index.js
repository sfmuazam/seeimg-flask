document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('camera');
    const captureButton = document.getElementById('capture-button');
    const switchCameraButton = document.getElementById('switch-camera');
    const resultContainer = document.getElementById('result-container');
    const cameraContainer = document.getElementById('camera-container');
    const uploadContainer = document.getElementById('upload-container');
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const capturedImage = document.getElementById('captured-image');
    const caption = document.getElementById('caption');
    const replayCaptionButton = document.getElementById('replay-caption-button');
    const stopCaptionButton = document.getElementById('stop-caption-button');
    const closeButton = document.getElementById('close-button');
    const cameraTab = document.getElementById('camera-tab');
    const uploadTab = document.getElementById('upload-tab');

    let currentStream;
    let useFrontCamera = true;
    let speechSynthesisUtterance;
    let recognition;
    let selectedVoice;

    let currentMode = 'camera';  

    const isAndroid = /android/i.test(navigator.userAgent);
    const initialFacingMode = isAndroid ? 'environment' : 'user';

    const constraints = {
        video: {
            facingMode: initialFacingMode,
            width: { ideal: 1280 },  
            height: { ideal: 720 } 
        }
    };

    cameraTab.addEventListener('click', () => {
        currentMode = 'camera';
        cameraContainer.classList.remove('hidden');
        uploadContainer.classList.add('hidden');
        resultContainer.classList.add('hidden');
        cameraTab.classList.add('bg-blue-500', 'text-white');
        cameraTab.classList.remove('bg-gray-300');
        uploadTab.classList.add('bg-gray-300');
        uploadTab.classList.remove('bg-blue-500', 'text-white');
        stopSpeaking();
        initCamera();
        startSpeechRecognition();
    });

    uploadTab.addEventListener('click', () => {
        currentMode = 'upload';
        cameraContainer.classList.add('hidden');
        uploadContainer.classList.remove('hidden');
        resultContainer.classList.add('hidden');
        uploadTab.classList.add('bg-blue-500', 'text-white');
        uploadTab.classList.remove('bg-gray-300');
        cameraTab.classList.add('bg-gray-300');
        cameraTab.classList.remove('bg-blue-500', 'text-white');
        stopSpeaking();
        stopCamera();
        stopSpeechRecognition();
        fileInput.value = '';
    });

    async function initCamera() {
        try {
            currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            video.srcObject = currentStream;
        } catch (error) {
            console.error('Error accessing the camera: ', error);
            alert('Tidak dapat mengakses kamera. Silakan periksa pengaturan browser Anda.');
        }
    }

    function stopCamera() {
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
            currentStream = null;
        }
    }

    captureButton.addEventListener('click', async () => {
        disableButtons(true);
        captureButton.textContent = 'Memproses...';

        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = canvas.toDataURL('image/png');
        capturedImage.src = imageData;

        stopCamera();
        video.srcObject = null;
        video.poster = imageData;

        await uploadImageAndGetCaption(imageData, 'camera');

        disableButtons(false);
        captureButton.textContent = 'Ambil Foto';
    });

    switchCameraButton.addEventListener('click', () => {
        useFrontCamera = !useFrontCamera;
        constraints.video.facingMode = useFrontCamera ? 'user' : 'environment';
        stopCamera();
        initCamera();
    });

    uploadButton.addEventListener('click', () => {
        const file = fileInput.files[0];
        if (!file) return;

        const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            alert('Format gambar tidak valid. Hanya menerima jpg, jpeg, png, dan webp.');
            return;
        }

        disableButtons(true);
        uploadButton.textContent = 'Memproses...';

        const reader = new FileReader();
        reader.onloadend = async () => {
            const imageData = reader.result;
            capturedImage.src = imageData;

            await uploadImageAndGetCaption(imageData, 'upload');
        };
        reader.readAsDataURL(file);
    });

    replayCaptionButton.addEventListener('click', () => {
        speakCaption(caption.textContent);
    });

    stopCaptionButton.addEventListener('click', () => {
        stopSpeaking();
    });

    closeButton.addEventListener('click', () => {
        resultContainer.classList.add('hidden');
        if (currentMode === 'camera') {
            cameraContainer.classList.remove('hidden');
            initCamera();
            startSpeechRecognition();
        } else if (currentMode === 'upload') {
            uploadContainer.classList.remove('hidden');
        }
        stopSpeaking();
    });

    async function uploadImageAndGetCaption(imageData, source) {
        try {
            const formData = new FormData();
            formData.append('file', dataURItoBlob(imageData), 'image.jpg');

            const response = await fetch('/captioning', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Failed to upload image');
            }

            const data = await response.json();
            const captionText = data.caption;
            caption.textContent = captionText;
            speakCaption(captionText);

            cameraContainer.classList.add('hidden');
            uploadContainer.classList.add('hidden');
            resultContainer.classList.remove('hidden');
        } catch (error) {
            console.error('Error:', error);
            showToastError('Terjadi kesalahan saat mengunggah gambar.');
        } finally {
            disableButtons(false);
            captureButton.textContent = 'Ambil Foto';
            uploadButton.textContent = 'Unggah';
        }
    }

    function dataURItoBlob(dataURI) {
        const byteString = atob(dataURI.split(',')[1]);
        const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0];
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        for (let i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
        }
        return new Blob([ab], { type: mimeString });
    }

    function speakCaption(text) {
        if ('speechSynthesis' in window) {
            speechSynthesisUtterance = new SpeechSynthesisUtterance(text);
            speechSynthesisUtterance.lang = 'id-ID';
            if (selectedVoice) {
                speechSynthesisUtterance.voice = selectedVoice;
            }
            window.speechSynthesis.speak(speechSynthesisUtterance);
        } else {
            showToastError('Sintesis suara tidak didukung di browser ini.');
        }
    }

    function stopSpeaking() {
        if (speechSynthesisUtterance) {
            window.speechSynthesis.cancel();
        }
    }

    function disableButtons(disable) {
        captureButton.disabled = disable;
        switchCameraButton.disabled = disable;
        uploadButton.disabled = disable;
        replayCaptionButton.disabled = disable;
        stopCaptionButton.disabled = disable;
        closeButton.disabled = disable;
    }

    function startSpeechRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.lang = 'id-ID';
            recognition.continuous = true;
            recognition.interimResults = false;

            recognition.onresult = (event) => {
                const transcript = event.results[event.results.length - 1][0].transcript.trim().toLowerCase();
                if (['foto', 'potret', 'tangkap', 'capture'].includes(transcript)) {
                    captureButton.click();
                }
            };

            recognition.onerror = (event) => {
                console.error('Kesalahan pengenalan suara:', event.error);
            };

            recognition.start();
        } else {
            showToastError('Pengenalan suara tidak didukung di browser ini.');
        }
    }

    function stopSpeechRecognition() {
        if (recognition) {
            recognition.stop();
            recognition = null;
        }
    }

    cameraTab.click();
});
