import * as THREE from 'three';

export function createUnderwaterSkybox(scene) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const context = canvas.getContext('2d');
    const gradient = context.createLinearGradient(0, 0, 0, 512);
    gradient.addColorStop(0, '#87CEEB');
    gradient.addColorStop(0.3, '#5599dd');
    gradient.addColorStop(0.5, '#3366aa');
    gradient.addColorStop(0.7, '#1e3c72');
    gradient.addColorStop(1, '#050515');
    context.fillStyle = gradient;
    context.fillRect(0, 0, 512, 512);
    const sunX = 256;
    const sunY = 50;
    const sunGradient = context.createRadialGradient(sunX, sunY, 0, sunX, sunY, 100);
    sunGradient.addColorStop(0, 'rgba(255, 251, 230, 0.8)');
    sunGradient.addColorStop(0.3, 'rgba(255, 245, 200, 0.5)');
    sunGradient.addColorStop(0.6, 'rgba(135, 206, 235, 0.3)');
    sunGradient.addColorStop(1, 'rgba(135, 206, 235, 0)');
    context.fillStyle = sunGradient;
    context.fillRect(sunX - 100, sunY - 100, 200, 200);
    context.globalAlpha = 0.15;
    const rayGradient = context.createRadialGradient(sunX, sunY, 20, sunX, sunY, 200);
    rayGradient.addColorStop(0, 'rgba(255, 251, 230, 1)');
    rayGradient.addColorStop(1, 'rgba(255, 251, 230, 0)');
    context.fillStyle = rayGradient;
    context.fillRect(sunX - 200, sunY - 200, 400, 400);
    context.globalAlpha = 1.0;
    const texture = new THREE.CanvasTexture(canvas);
    texture.mapping = THREE.EquirectangularReflectionMapping;
    const skyGeometry = new THREE.SphereGeometry(100, 32, 32);
    const skyMaterial = new THREE.MeshBasicMaterial({ map: texture, side: THREE.BackSide, depthWrite: false });
    const skybox = new THREE.Mesh(skyGeometry, skyMaterial);
    scene.add(skybox);
    // return canvas;
}

export function createSpaceSkybox(scene) {
    const canvas = document.createElement('canvas');
    canvas.width = 2048;
    canvas.height = 1024;
    const context = canvas.getContext('2d');
    const bgGradient = context.createLinearGradient(0, 0, 2048, 1024);
    bgGradient.addColorStop(0, '#000308');
    bgGradient.addColorStop(0.3, '#020108');
    bgGradient.addColorStop(0.6, '#000205');
    bgGradient.addColorStop(1, '#000104');
    context.fillStyle = bgGradient;
    context.fillRect(0, 0, 2048, 1024);
    context.globalAlpha = 0.03;
    const nebula1 = context.createRadialGradient(500, 300, 0, 500, 300, 300);
    nebula1.addColorStop(0, '#ff00ff');
    nebula1.addColorStop(0.5, '#8800ff');
    nebula1.addColorStop(1, 'transparent');
    context.fillStyle = nebula1;
    context.fillRect(200, 0, 600, 600);
    const nebula2 = context.createRadialGradient(1500, 700, 0, 1500, 700, 400);
    nebula2.addColorStop(0, '#00ffff');
    nebula2.addColorStop(0.5, '#0088ff');
    nebula2.addColorStop(1, 'transparent');
    context.fillStyle = nebula2;
    context.fillRect(1100, 300, 800, 800);
    context.globalAlpha = 1.0;
    function drawStar(x, y, brightness, size, color) {
        const glowSize = size * 3;
        const glow = context.createRadialGradient(x, y, 0, x, y, glowSize);
        glow.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, ${brightness})`);
        glow.addColorStop(0.5, `rgba(${color.r}, ${color.g}, ${color.b}, ${brightness * 0.3})`);
        glow.addColorStop(1, 'transparent');
        context.fillStyle = glow;
        context.fillRect(x - glowSize, y - glowSize, glowSize * 2, glowSize * 2);
        context.fillStyle = `rgba(255, 255, 255, ${brightness})`;
        context.fillRect(x - size/2, y - size/2, size, size);
    }
    for (let i = 0; i < 50; i++) {
        const x = Math.random() * 2048;
        const y = Math.random() * 1024;
        const brightness = 0.6 + Math.random() * 0.4;
        const size = 1 + Math.random() * 2;
        const color = { r: 200 + Math.random() * 55, g: 200 + Math.random() * 55, b: 255 };
        drawStar(x, y, brightness, size, color);
    }
    for (let i = 0; i < 200; i++) {
        const x = Math.random() * 2048;
        const y = Math.random() * 1024;
        const brightness = 0.3 + Math.random() * 0.3;
        const size = 0.5 + Math.random();
        const color = { r: 180 + Math.random() * 75, g: 180 + Math.random() * 75, b: 200 + Math.random() * 55 };
        drawStar(x, y, brightness, size, color);
    }
    for (let i = 0; i < 1000; i++) {
        const x = Math.random() * 2048;
        const y = Math.random() * 1024;
        const brightness = 0.1 + Math.random() * 0.2;
        context.fillStyle = `rgba(255, 255, 255, ${brightness})`;
        context.fillRect(x, y, 1, 1);
    }
    for (let i = 0; i < 20; i++) {
        const x = Math.random() * 2048;
        const y = Math.random() * 1024;
        const colors = [
            {r: 255, g: 200, b: 150},
            {r: 150, g: 200, b: 255},
            {r: 255, g: 150, b: 150}
        ];
        const color = colors[Math.floor(Math.random() * colors.length)];
        const brightness = 0.5 + Math.random() * 0.3;
        drawStar(x, y, brightness, 1.5, color);
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.mapping = THREE.EquirectangularReflectionMapping;
    const skyGeometry = new THREE.SphereGeometry(100, 64, 32);
    const skyMaterial = new THREE.MeshBasicMaterial({ map: texture, side: THREE.BackSide, depthWrite: false });
    const skybox = new THREE.Mesh(skyGeometry, skyMaterial);
    scene.add(skybox);
    // return canvas;
}

export function createConstellationSkybox(scene) {
    // Load the star constellation cubemap
    // const loader = new THREE.CubeTextureLoader();
    // const texture = loader.load(['star_constellation_cubemap.jpg']);
    // scene.background = texture;

    const loader = new THREE.TextureLoader().setPath('./images/');
    // const texture = loader.load('star_constellation_cubemap.jpg');
    const texture = loader.load('constellation_figures_2k_gal.jpg');

    // texture.mapping = THREE.CubeReflectionMapping;
    texture.mapping = THREE.EquirectangularReflectionMapping;
    // texture.colorSpace = THREE.SRGBColorSpace;

    // Create a large cube to serve as the skybox (better for cubemaps)
    const skyGeometry = new THREE.BoxGeometry(100, 100, 100);
    const skyMaterial = new THREE.MeshBasicMaterial({
        envMap: texture,
        side: THREE.BackSide,
        depthWrite: false,
        color: new THREE.Color("0x020204"),
    });

    const skybox = new THREE.Mesh(skyGeometry, skyMaterial);
    scene.add(skybox);

    // // See https://threejs.org/manual/examples/background-equirectangularmap.html
    // const loader = new THREE.TextureLoader().setPath('./images/');
    // const texture = loader.load(
    //     // 'milkyway_2020_1280.png',
    //     'constellation_figures_2k_gal.jpg',
    //     () => {
    //         texture.mapping = THREE.EquirectangularReflectionMapping;
    //         texture.colorSpace = THREE.SRGBColorSpace;
    //         scene.background = texture;
    //         // make it fainter and bluer
    //         scene.backgroundIntensity = 0.1; // Doesn't seem to do anything.
    //     } );

    return null;
}

export function addSkybox(scene, type = 'space') {
    if (type === 'underwater') return createUnderwaterSkybox(scene);
    if (type === 'space') return createSpaceSkybox(scene);
    if (type === 'constellation') return createConstellationSkybox(scene);
}
