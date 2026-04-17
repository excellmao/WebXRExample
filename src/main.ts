import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

// ─── 1. INITIALIZE VIEWER ──────────────────────────────────────────────────
const viewer = new GaussianSplats3D.Viewer({
    rootElement: document.getElementById('app')!,
    sharedMemoryForWorkers: false,
    selfDrivenMode: true,
    useBuiltInControls: false,
    webXRMode: GaussianSplats3D.WebXRMode.VR,
    gpuAcceleratedSort: true,
    sphericalHarmonicsDegree: 2,
});

// PlayCanvas Colors
const renderer = (viewer as any).renderer || (viewer as any).webGLRenderer;
if (renderer) {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
}

// ─── 2. SETUP CAMERA (NO RIG!) ─────────────────────────────────────────────
viewer.start();
const internalScene = viewer.scene || viewer.threeScene;

// Set the rotation order so mouse look doesn't flip upside down
viewer.camera.rotation.order = 'YXZ';

// 1. Soft, universal Ambient Light (lights up the dark areas evenly)
const gsAmbientLight = new THREE.AmbientLight(0xffffff, 1.0);
internalScene.add(gsAmbientLight);

const gsSunLight = new THREE.DirectionalLight(0xffffff, 1.5);
gsSunLight.position.set(5, 10, 7);
internalScene.add(gsSunLight);

// ─── 3. WASD & MOUSE LOOK CONTROLS ─────────────────────────────────────────
const keys: Record<string, boolean> = {};
window.addEventListener('keydown', (e) => keys[e.code] = true);
window.addEventListener('keyup', (e) => keys[e.code] = false);

let isDragging = false;
let prevMouse = { x: 0, y: 0 };

document.getElementById('app')!.addEventListener('mousedown', (e) => {
    if (e.button === 0) { isDragging = true; prevMouse = { x: e.clientX, y: e.clientY }; }
});
window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const deltaX = e.clientX - prevMouse.x;
    const deltaY = e.clientY - prevMouse.y;
    prevMouse = { x: e.clientX, y: e.clientY };

    // Rotate the camera DIRECTLY
    viewer.camera.rotation.y -= deltaX * 0.002;
    viewer.camera.rotation.x -= deltaY * 0.002;
    viewer.camera.rotation.x = Math.max(-Math.PI/2, Math.min(Math.PI/2, viewer.camera.rotation.x));
});
window.addEventListener('mouseup', (e) => { if (e.button === 0) isDragging = false; });

function updateMovement() {
    const moveSpeed = 0.05;
    const direction = new THREE.Vector3();
    const cameraQuat = new THREE.Quaternion();

    viewer.camera.getWorldQuaternion(cameraQuat);
    const front = new THREE.Vector3(0, 0, -1).applyQuaternion(cameraQuat);
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(cameraQuat);

    if (keys['KeyW']) direction.add(front);
    if (keys['KeyS']) direction.sub(front);
    if (keys['KeyD']) direction.add(right);
    if (keys['KeyA']) direction.sub(right);

    if (direction.lengthSq() > 0) {
        direction.normalize().multiplyScalar(moveSpeed);
        // Move the camera DIRECTLY
        viewer.camera.position.add(direction);
    }
    requestAnimationFrame(updateMovement);
}
updateMovement();

// ─── 4. DYNAMIC MODEL LOADER ───────────────────────────────────────────────
const modelSelect = document.getElementById('model-select') as HTMLSelectElement;
const loadingText = document.getElementById('loading-text')!;

const plyFiles = import.meta.glob('/public/*.ply');
const availableModels = Object.keys(plyFiles).map(path => path.replace('/public', ''));

availableModels.forEach(modelPath => {
    const option = document.createElement('option');
    option.value = modelPath;
    option.innerText = modelPath.replace('/', '').replace('.ply', '').replace(/_/g, ' ');
    modelSelect.appendChild(option);
});

let currentSceneIndex = -1;
let isSwapping = false;

async function loadSplatModel(modelPath: string) {
    if (isSwapping) return;
    try {
        isSwapping = true;
        modelSelect.disabled = true;
        loadingText.innerText = "Loading Model...";

        if (currentSceneIndex !== -1) {
            await (viewer as any).removeSplatScene(currentSceneIndex);
        }

        await viewer.addSplatScene(modelPath, {
            splatAlphaRemovalThreshold: 5,
            showLoadingUI: false,
            rotation: [1, 0, 0, 0],
        });

        currentSceneIndex = 0;

        // Auto-Center math applied directly to the camera!
        const boundingBox = new THREE.Box3().setFromObject(internalScene);
        const center = new THREE.Vector3();
        boundingBox.getCenter(center);

        // Place the user in the middle of the room, standing 1.6m high
        viewer.camera.position.set(center.x, center.y + 1.6, center.z);

        // Look straight ahead
        viewer.camera.rotation.set(0, 0, 0);

        loadingText.innerText = "";

    } catch (e) {
        console.error(e);
        loadingText.innerText = "Error loading model!";
    } finally {
        isSwapping = false;
        modelSelect.disabled = false;
    }
}

modelSelect.addEventListener('change', (e) => {
    loadSplatModel((e.target as HTMLSelectElement).value);
});

if (availableModels.length > 0) {
    loadSplatModel(availableModels[0]);
} else {
    loadingText.innerText = "No .ply files found in /public";
}

// ─── 5. TAB SWITCHING LOGIC ────────────────────────────────────────────────
const btn3DGS = document.getElementById('btn-3dgs')!;
const btnMidas = document.getElementById('btn-midas')!;
const appContainer = document.getElementById('app')!;
const uiPanel = document.getElementById('ui-panel')!;
const midasContainer = document.getElementById('midas-container')!;
const uploadPanel = document.getElementById('upload-panel')!;

btn3DGS.addEventListener('click', () => {
    // Update Buttons
    btn3DGS.classList.add('active');
    btnMidas.classList.remove('active');

    // Show 3DGS, Hide MiDaS
    appContainer.style.display = 'block';
    uiPanel.style.display = 'block';
    midasContainer.style.display = 'none';
    uploadPanel.style.display = 'none';
    document.getElementById('ai-spawn-panel')!.style.display = 'flex';
    // Resume splat rendering
    // Note: Your WebXR button might need to be repositioned or toggled here later
});

btnMidas.addEventListener('click', () => {
    // Update Buttons
    btnMidas.classList.add('active');
    btn3DGS.classList.remove('active');

    // Show MiDaS, Hide 3DGS
    appContainer.style.display = 'none';
    uiPanel.style.display = 'none';
    midasContainer.style.display = 'block';
    uploadPanel.style.display = 'block';
    document.getElementById('ai-spawn-panel')!.style.display = 'none';
});

// ─── 6. MIDAS 2.5D HOLOGRAPHIC VIEWER ──────────────────────────────────────
const imageUpload = document.getElementById('image-upload') as HTMLInputElement;

// 1. Set up a dedicated Three.js scene for the photo
const midasScene = new THREE.Scene();
const midasCamera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const midasRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
midasRenderer.setSize(window.innerWidth, window.innerHeight);
midasContainer.appendChild(midasRenderer.domElement);

// Add some light so the 3D texture is visible
const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
midasScene.add(ambientLight);

// 2. Create the Canvas (The Plane)
const planeGeometry = new THREE.PlaneGeometry(10, 10, 256, 256);

const planeMaterial = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    side: THREE.DoubleSide,
    displacementScale: 0.5,
    displacementBias: -0.2,
});

const photoPlane = new THREE.Mesh(planeGeometry, planeMaterial);
midasScene.add(photoPlane);
midasCamera.position.z = 8;

// 3. Parallax Wobble Effect - THE OLD WAY
let mouseX = 0;
let mouseY = 0;

window.addEventListener('mousemove', (event) => {
    if (midasContainer.style.display !== 'block') return;
    // Track mouse position
    mouseX = (event.clientX - window.innerWidth / 2) * 0.0005;
    mouseY = (event.clientY - window.innerHeight / 2) * 0.0005;
});

function animateMidas() {
    requestAnimationFrame(animateMidas);
    if (midasContainer.style.display === 'block') {
        // Physically tilt the photo plane
        photoPlane.rotation.y += (mouseX - photoPlane.rotation.y) * 0.05;
        photoPlane.rotation.x += (mouseY - photoPlane.rotation.x) * 0.05;
        midasRenderer.render(midasScene, midasCamera);
    }
}
animateMidas();

// ─── 4. THE API BRIDGE & UI LOGIC ──────────────────────────────────────────
let currentOriginalTex: any = null;
let currentDepthTex: any = null;
let isShowingDepth = false;

const btnToggleDepth = document.getElementById('btn-toggle-depth') as HTMLButtonElement;
const uploadLabel = document.querySelector('#upload-panel label') as HTMLElement;

// --- The Toggle Button ---
btnToggleDepth.addEventListener('click', () => {
    if (!currentOriginalTex || !currentDepthTex) return;

    isShowingDepth = !isShowingDepth;
    planeMaterial.map = isShowingDepth ? currentDepthTex : currentOriginalTex;
    planeMaterial.needsUpdate = true;

    btnToggleDepth.innerText = isShowingDepth ? "🖼️ View Original Photo" : "🔍 View Depth Map";
    btnToggleDepth.style.background = isShowingDepth ? "#FF9800" : "#2196F3";
});

// --- The Core AI Pipeline ---
async function runMidasAI(fileOrBlob: File | Blob) {
    const uploadLabel = document.querySelector('#upload-panel label') as HTMLElement;
    const btnToggleDepth = document.getElementById('btn-toggle-depth') as HTMLButtonElement;

    uploadLabel.innerText = "🤖 RUNNING AI... PLEASE WAIT";
    uploadLabel.style.color = "#FFD700";
    btnToggleDepth.style.display = "none";

    const formData = new FormData();
    formData.append('image', fileOrBlob, "image.jpg");

    try {
        const response = await fetch('http://127.0.0.1:5000/api/midas', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Python Server Rejected the Request");

        const depthBlob = await response.blob();
        const depthUrl = URL.createObjectURL(depthBlob);
        const originalUrl = URL.createObjectURL(fileOrBlob);

        const textureLoader = new THREE.TextureLoader();
        currentOriginalTex = await textureLoader.loadAsync(originalUrl);
        currentDepthTex = await textureLoader.loadAsync(depthUrl);

        const aspect = currentOriginalTex.image.width / currentOriginalTex.image.height;
        photoPlane.scale.set(aspect, 1, 1);

        // 🌟 APPLY TO STANDARD MATERIAL
        isShowingDepth = false;
        planeMaterial.map = currentOriginalTex;
        planeMaterial.displacementMap = currentDepthTex;
        planeMaterial.needsUpdate = true;

        btnToggleDepth.style.display = "block";
        btnToggleDepth.innerText = "🔍 View Depth Map";
        uploadLabel.innerText = "✨ MAGIC COMPLETE!";
        uploadLabel.style.color = "#4CAF50";

    } catch (err) {
        console.error("AI Error:", err);
        uploadLabel.innerText = "❌ ERROR: CHECK CONSOLE";
        uploadLabel.style.color = "#FF4444";
    }
}

// --- Standard Toggle Logic ---
btnToggleDepth.addEventListener('click', () => {
    if (!currentOriginalTex || !currentDepthTex) return;
    isShowingDepth = !isShowingDepth;

    // Switch the primary map
    planeMaterial.map = isShowingDepth ? currentDepthTex : currentOriginalTex;
    planeMaterial.needsUpdate = true;

    btnToggleDepth.innerText = isShowingDepth ? "🖼️ View Original Photo" : "🔍 View Depth Map";
    btnToggleDepth.style.background = isShowingDepth ? "#FF9800" : "#2196F3";
});

// --- Simple File Input Listener ---
imageUpload.addEventListener('change', (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (file) runMidasAI(file);
});

// --- Toggle Button Fix ---
// Since we are using a Shader, we need to swap the uTexture uniform, not material.map
btnToggleDepth.addEventListener('click', () => {
    if (!currentOriginalTex || !currentDepthTex) return;

    isShowingDepth = !isShowingDepth;

    // Update the Shader Uniforms
    planeMaterial.uniforms.uTexture.value = isShowingDepth ? currentDepthTex : currentOriginalTex;

    btnToggleDepth.innerText = isShowingDepth ? "🖼️ View Original Photo" : "🔍 View Depth Map";
    btnToggleDepth.style.background = isShowingDepth ? "#FF9800" : "#2196F3";
});

// Handle window resizing
window.addEventListener('resize', () => {
    midasCamera.aspect = window.innerWidth / window.innerHeight;
    midasCamera.updateProjectionMatrix();
    midasRenderer.setSize(window.innerWidth, window.innerHeight);

    // Also update 3DGS camera
    viewer.camera.aspect = window.innerWidth / window.innerHeight;
    viewer.camera.updateProjectionMatrix();
});

// --- Text-to-3D Spawning Logic ---
const aiPromptInput = document.getElementById('ai-prompt-input') as HTMLInputElement;
const btnSpawnAi = document.getElementById('btn-spawn-ai') as HTMLButtonElement;
const gltfLoader = new GLTFLoader();

btnSpawnAi.addEventListener('click', async () => {
    const prompt = aiPromptInput.value.trim();
    if (!prompt) return;

    // UI Feedback
    const originalText = btnSpawnAi.innerText;
    btnSpawnAi.innerText = "⏳ Generating 3D...";
    btnSpawnAi.disabled = true;
    btnSpawnAi.style.background = "#555";

    try {
        // 1. Ask Python to generate the model
        const response = await fetch('http://127.0.0.1:5000/api/text-to-3d', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        });

        if (!response.ok) throw new Error("Backend failed to generate model");

        // 2. Receive the .glb file as a blob
        const modelBlob = await response.blob();
        const modelUrl = URL.createObjectURL(modelBlob);

        // 3. Load the model into Three.js
        gltfLoader.load(modelUrl, (gltf) => {
            const model = gltf.scene;

            // 🌟 THE MATH: Calculate exactly 2 meters in front of the camera
            const spawnDistance = 2.0;
            const cameraDirection = new THREE.Vector3();
            viewer.camera.getWorldDirection(cameraDirection);

            // Start at camera position, move forward by 'spawnDistance'
            const spawnPos = new THREE.Vector3()
                .copy(viewer.camera.position)
                .add(cameraDirection.multiplyScalar(spawnDistance));

            // Set Position and make it face the camera
            model.position.copy(spawnPos);
            model.lookAt(viewer.camera.position);

            // Scale it down (AI models are often massive)
            model.scale.set(0.5, 0.5, 0.5);

            // Inject it into the Gaussian Splat scene!
            internalScene.add(model);

            // Reset UI
            btnSpawnAi.innerText = "✅ Spawned!";
            btnSpawnAi.style.background = "#4CAF50";
            setTimeout(() => {
                btnSpawnAi.innerText = originalText;
                btnSpawnAi.disabled = false;
                btnSpawnAi.style.background = "#E91E63";
                aiPromptInput.value = "";
            }, 2000);
        });

    } catch (error) {
        console.error(error);
        btnSpawnAi.innerText = "❌ Error";
        btnSpawnAi.style.background = "#FF4444";
        setTimeout(() => {
            btnSpawnAi.innerText = originalText;
            btnSpawnAi.disabled = false;
            btnSpawnAi.style.background = "#E91E63";
        }, 2000);
    }
});