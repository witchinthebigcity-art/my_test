(function () {
    const STYLE_CONFIGS = {
        neon: {skin: 0xf2b083, hair: 0x13bde1, hair2: 0x49f04d, top: 0xdfe7eb, accent: 0x39ed42, bottom: 0x151821, shoes: 0x35f04a, accessory: 'headphones', hairKind: 'spiky', headShape: 'square'},
        basket: {skin: 0xd99362, hair: 0x5a2e20, top: 0x16191b, accent: 0xff7425, bottom: 0x26282b, shoes: 0xf1f1ef, accessory: 'basketball', hairKind: 'spiky', headShape: 'square'},
        pixel: {skin: 0xf2af9b, hair: 0xff82c0, hair2: 0x35caef, top: 0xf7f8fa, accent: 0xff4aa6, bottom: 0x2c9ee8, shoes: 0xf7f8fa, accessory: 'controller', hairKind: 'long', cap: 0xf4f7fb, headShape: 'round'},
        'pink-wave': {skin: 0xf2b69b, hair: 0xffd2ba, hair2: 0xff8fc1, top: 0xff86bb, accent: 0xffffff, bottom: 0x42a9db, shoes: 0xff8fbd, accessory: 'controller', hairKind: 'long', headShape: 'round'},
        'white-street': {skin: 0xdca078, hair: 0x33251f, top: 0xf0f1f1, accent: 0xe43b35, bottom: 0x151719, shoes: 0xf2f1ec, accessory: 'glasses', hairKind: 'short', hat: 0xf0f0ed, headShape: 'square'},
        'aqua-pop': {skin: 0xf0aa83, hair: 0x202332, hair2: 0xff79aa, top: 0xff68a3, accent: 0x31d3da, bottom: 0x29cad2, shoes: 0x35d0d4, accessory: 'bracelets', hairKind: 'long', cap: 0xff6fa9, headShape: 'square'},
        turbo: {skin: 0xe0ac82, hair: 0x38271f, top: 0x153f70, accent: 0xd9a83e, bottom: 0x202633, shoes: 0x8b5a2b, accessory: 'chain', hairKind: 'none', headShape: 'rounded', sleeve: 0xf2efe7, equipment: 'steampunk'},
        'cozy-plaid': {skin: 0xa96f50, hair: 0x151318, top: 0xf2f2f0, accent: 0xa52d36, bottom: 0x3b2228, shoes: 0xf3f1ed, accessory: 'earmuffs', hairKind: 'long', headShape: 'round', outfit: 'plaid'},
        'soft-blue': {skin: 0xdba881, hair: 0xe8c7b0, top: 0xf7f5f3, accent: 0xe9eef4, bottom: 0x8495a8, shoes: 0xf3f2ed, accessory: 'bows', hairKind: 'long', headShape: 'round', outfit: 'wide-pants'},
        'bronze-gent': {skin: 0xd4a078, hair: 0x4b2d1b, top: 0x8b531f, accent: 0xd49a3c, bottom: 0x6e421f, shoes: 0x9b662b, accessory: 'chain', hairKind: 'none', headShape: 'rounded', sleeve: 0x8b531f, equipment: 'bronze-suit'},
        'gym-hero': {skin: 0xb98667, hair: 0x111317, top: 0x111216, accent: 0xcb3e83, bottom: 0x16171a, shoes: 0xefefec, accessory: 'none', hairKind: 'swept', headShape: 'rounded', build: 'strong'},
        'capy-cozy': {skin: 0xe4b390, hair: 0x8a7168, top: 0xf6f3ef, accent: 0x8b6957, bottom: 0x6b5449, shoes: 0xf2efea, accessory: 'none', hairKind: 'long', headShape: 'round', equipment: 'capy-hat'},
        'city-white': {skin: 0xb67c5f, hair: 0x4b332b, top: 0xf5f2ed, accent: 0xd9d5cf, bottom: 0xc28e72, shoes: 0xf3f0ea, accessory: 'glasses', hairKind: 'long', headShape: 'round', equipment: 'handbag'},
        'dog-varsity': {skin: 0xa86f50, hair: 0x40251f, top: 0x43322b, accent: 0xe9e1d2, bottom: 0x7f8588, shoes: 0xf1efea, accessory: 'none', hairKind: 'long', headShape: 'round', equipment: 'dog-varsity'},
        'snow-dream': {skin: 0xd6a27f, hair: 0xe7c9b7, top: 0xf7f8f6, accent: 0xdce7ea, bottom: 0xf5f6f3, shoes: 0xf1f2ef, accessory: 'none', hairKind: 'long', headShape: 'round', equipment: 'snow-dress'},
        'festive-forge': {skin: 0xe0aa8e, hair: 0x7b2a22, top: 0xd72e28, accent: 0xf1b83d, bottom: 0xb92222, shoes: 0x3b241d, accessory: 'none', hairKind: 'none', headShape: 'rounded', equipment: 'festive'},
        'cardboard-bot': {skin: 0xb8874f, hair: 0x6b4d2e, top: 0x9a6b36, accent: 0x4a674d, bottom: 0x6c6c68, shoes: 0xe9e3d5, accessory: 'none', hairKind: 'none', headShape: 'square', sleeve: 0x7e7a6d, equipment: 'cardboard-bot'},
    };

    let currentViewer = null;

    function material(color, roughness = 0.72, metalness = 0.04) {
        return new THREE.MeshStandardMaterial({color, roughness, metalness, flatShading: false});
    }

    function addMesh(group, geometry, color, position, rotation = null, scale = null, options = {}) {
        const mesh = new THREE.Mesh(geometry, material(color, options.roughness, options.metalness));
        mesh.position.set(...position);
        if (rotation) mesh.rotation.set(...rotation);
        if (scale) mesh.scale.set(...scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        group.add(mesh);
        return mesh;
    }

    function box(group, size, position, color, rotation = null) {
        return addMesh(group, new THREE.BoxGeometry(...size), color, position, rotation);
    }

    function sphere(group, radius, position, color, scale = null) {
        return addMesh(group, new THREE.SphereGeometry(radius, 28, 20), color, position, null, scale);
    }

    function cylinder(group, radiusTop, radiusBottom, height, position, color, rotation = null) {
        return addMesh(group, new THREE.CylinderGeometry(radiusTop, radiusBottom, height, 32), color, position, rotation);
    }

    function torus(group, radius, tube, position, color, rotation = null) {
        return addMesh(group, new THREE.TorusGeometry(radius, tube, 12, 36), color, position, rotation, null, {roughness: .4, metalness: .35});
    }

    function roundedBox(group, size, radius, position, color) {
        const [width, height, depth] = size;
        const halfWidth = width / 2;
        const halfHeight = height / 2;
        const safeRadius = Math.min(radius, halfWidth, halfHeight);
        const shape = new THREE.Shape();
        shape.moveTo(-halfWidth + safeRadius, -halfHeight);
        shape.lineTo(halfWidth - safeRadius, -halfHeight);
        shape.quadraticCurveTo(halfWidth, -halfHeight, halfWidth, -halfHeight + safeRadius);
        shape.lineTo(halfWidth, halfHeight - safeRadius);
        shape.quadraticCurveTo(halfWidth, halfHeight, halfWidth - safeRadius, halfHeight);
        shape.lineTo(-halfWidth + safeRadius, halfHeight);
        shape.quadraticCurveTo(-halfWidth, halfHeight, -halfWidth, halfHeight - safeRadius);
        shape.lineTo(-halfWidth, -halfHeight + safeRadius);
        shape.quadraticCurveTo(-halfWidth, -halfHeight, -halfWidth + safeRadius, -halfHeight);
        const geometry = new THREE.ExtrudeGeometry(shape, {
            depth,
            bevelEnabled: true,
            bevelSegments: 3,
            bevelSize: .045,
            bevelThickness: .045,
        });
        geometry.center();
        return addMesh(group, geometry, color, position);
    }

    function limbBetween(group, start, end, width, depth, color) {
        const dx = end[0] - start[0];
        const dy = end[1] - start[1];
        const length = Math.hypot(dx, dy) + .08;
        const center = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2, (start[2] + end[2]) / 2];
        return box(group, [width, length, depth], center, color, [0, 0, -Math.atan2(dx, dy)]);
    }

    function buildHair(group, config) {
        const color = config.hair;
        if (config.hairKind === 'none') return;
        if (config.headShape === 'round') {
            sphere(group, .82, [0, 2.2, -.2], color, [1.06, 1.08, .92]);
            if (config.hairKind === 'long') {
                for (let index = 0; index < 6; index += 1) {
                    const side = index < 3 ? -1 : 1;
                    const row = index % 3;
                    const strandColor = row === 1 && config.hair2 ? config.hair2 : color;
                    sphere(group, .3, [side * (.72 + row * .1), 1.75 - row * .38, -.12], strandColor, [.72, 1.65, .64]);
                }
            }
            return;
        }

        box(group, [1.46, .3, 1.27], [0, 2.72, -.02], color);
        if (config.hairKind === 'spiky') {
            for (let index = 0; index < 7; index += 1) {
                const x = -.62 + index * .21;
                const strandColor = index % 3 === 0 && config.hair2 ? config.hair2 : color;
                addMesh(group, new THREE.ConeGeometry(.18, .62, 8), strandColor, [x, 3.0 + (index % 2) * .08, -.02], [0, 0, (index - 3) * -.08]);
            }
        } else if (config.hairKind === 'long') {
            box(group, [.25, 1.18, 1.08], [-.73, 1.92, -.08], color);
            box(group, [.25, 1.18, 1.08], [.73, 1.92, -.08], config.hair2 || color);
        } else if (config.hairKind === 'swept') {
            for (let index = 0; index < 5; index += 1) {
                box(group, [.5, .22, .48], [-.42 + index * .19, 2.78 + index * .06, .18], color, [0, 0, -.28]);
            }
        }
    }

    function buildFace(group, config) {
        const faceZ = config.headShape === 'round' ? .76 : .69;
        sphere(group, .095, [-.27, 2.18, faceZ], 0x17222a, [.82, 1.28, .46]);
        sphere(group, .095, [.27, 2.18, faceZ], 0x17222a, [.82, 1.28, .46]);
        sphere(group, .14, [0, 1.92, faceZ + .01], 0x7c3440, [1.28, .45, .32]);
        sphere(group, .06, [0, 1.95, faceZ + .045], 0xffffff, [1.25, .35, .22]);
        if (config.accessory === 'glasses') {
            box(group, [.55, .3, .07], [-.31, 2.2, faceZ + .05], 0x111417);
            box(group, [.55, .3, .07], [.31, 2.2, faceZ + .05], 0x111417);
            box(group, [.14, .07, .07], [0, 2.2, faceZ + .06], 0x111417);
        }
    }

    function buildArms(group, config) {
        const strong = config.build === 'strong';
        const shoulderX = strong ? .9 : .76;
        const armWidth = strong ? .68 : .52;
        const forearmWidth = strong ? .5 : .39;
        const leftShoulder = [-shoulderX, .98, 0];
        const rightShoulder = [shoulderX, .98, 0];
        let leftElbow = [strong ? -1.22 : -1.04, .32, .06];
        let rightElbow = [strong ? 1.22 : 1.04, .32, .06];
        let leftHand = [strong ? -1.2 : -1.04, -.3, .1];
        let rightHand = [strong ? 1.2 : 1.04, -.3, .1];

        if (config.accessory === 'controller') {
            leftHand = [-.58, -.22, .55];
            rightHand = [.58, -.22, .55];
        } else if (config.accessory === 'basketball') {
            leftElbow = [-1.12, .82, .16];
            leftHand = [-1.24, 1.12, .42];
        }

        limbBetween(group, leftShoulder, leftElbow, armWidth, strong ? .68 : .6, config.sleeve || config.top);
        limbBetween(group, rightShoulder, rightElbow, armWidth, strong ? .68 : .6, config.sleeve || config.top);
        limbBetween(group, leftElbow, leftHand, forearmWidth, strong ? .56 : .46, config.skin);
        limbBetween(group, rightElbow, rightHand, forearmWidth, strong ? .56 : .46, config.skin);
        sphere(group, strong ? .32 : .27, leftHand, config.skin, [.9, 1, .82]);
        sphere(group, strong ? .32 : .27, rightHand, config.skin, [.9, 1, .82]);
        if (strong) {
            sphere(group, .38, leftShoulder, config.skin, [1, 1.08, .9]);
            sphere(group, .38, rightShoulder, config.skin, [1, 1.08, .9]);
        }
        return {leftHand, rightHand};
    }

    function buildAccessories(group, config, pose) {
        if (config.equipment === 'steampunk') {
            const gold = 0xd9a83e;
            const bronze = 0x7d4b25;
            const cyan = 0x55d9f0;
            cylinder(group, .61, .72, .82, [0, 3.08, -.01], 0x2a211d);
            cylinder(group, .98, .98, .1, [0, 2.66, .02], bronze);
            box(group, [1.25, .16, .06], [0, 2.82, .53], gold);
            [-.31, .31].forEach((x) => {
                torus(group, .18, .055, [x, 2.98, .6], gold);
                cylinder(group, .13, .13, .055, [x, 2.98, .61], cyan, [Math.PI / 2, 0, 0]);
                sphere(group, .035, [x - .035, 3.015, .66], 0xffffff);
            });

            [-1, 1].forEach((side) => {
                box(group, [.62, .58, .62], [side * 1.03, .03, .1], gold, [0, 0, side * -.05]);
                box(group, [.68, .16, .66], [side * 1.03, .31, .1], bronze);
                sphere(group, .09, [side * 1.03, .13, .43], cyan, [.72, .72, .34]);
                box(group, [.66, .32, .71], [side * .42, -1.12, .05], bronze);
                box(group, [.7, .17, .75], [side * .42, -1.34, .07], gold);
                box(group, [.72, .2, .78], [side * .42, -1.58, .08], bronze);
            });

            box(group, [.32, .23, .06], [0, 1.13, .47], config.sleeve);
            box(group, [.12, .48, .07], [0, .92, .49], 0x18202d);
            sphere(group, .055, [0, .72, .5], gold, [1, 1, .45]);
            sphere(group, .055, [0, .52, .5], gold, [1, 1, .45]);
            box(group, [1.42, .2, .95], [0, -.23, 0], bronze);
            box(group, [.27, .28, .07], [0, -.23, .5], gold);
        }
        if (config.accessory === 'earmuffs') {
            addMesh(group, new THREE.TorusGeometry(.8, .075, 12, 32, Math.PI), 0xf4f2ef, [0, 2.3, -.05]);
            sphere(group, .26, [-.79, 2.18, 0], 0xf8f7f3, [.62, 1.05, .7]);
            sphere(group, .26, [.79, 2.18, 0], 0xf8f7f3, [.62, 1.05, .7]);
        }
        if (config.accessory === 'bows') {
            [-1, 1].forEach((side) => {
                sphere(group, .14, [side * .42, -.55, .43], 0xf7f5f1, [1.4, .7, .38]);
                sphere(group, .14, [side * .66, -.55, .43], 0xf7f5f1, [1.4, .7, .38]);
                box(group, [.07, .62, .04], [side * .54, -.82, .46], 0xf7f5f1, [0, 0, side * .12]);
            });
        }
        if (config.equipment === 'bronze-suit') {
            const bronze = 0x9a672d;
            const gold = 0xd7a244;
            cylinder(group, .59, .68, .72, [0, 3.02, 0], bronze);
            cylinder(group, .94, .94, .09, [0, 2.67, .02], gold);
            [0, 1, 2].forEach((index) => {
                sphere(group, .065, [-.24 + index * .24, 3.08, .58], 0x2c241e, [1, 1, .45]);
            });
            box(group, [.35, .38, .08], [0, .85, .49], 0xf0e3ce);
            box(group, [.12, .55, .09], [0, .62, .5], 0x3a2d26);
            [-1, 1].forEach((side) => {
                box(group, [.62, .34, .64], [side * 1.02, .6, .03], gold, [0, 0, side * .15]);
                sphere(group, .07, [side * 1.02, .62, .39], 0x2b2928, [1, 1, .4]);
            });
        }
        if (config.equipment === 'capy-hat') {
            sphere(group, .72, [0, 2.83, -.02], 0x97725d, [1.08, .58, .93]);
            sphere(group, .2, [-.48, 3.12, -.02], 0x7d5b49, [.8, 1, .75]);
            sphere(group, .2, [.48, 3.12, -.02], 0x7d5b49, [.8, 1, .75]);
            sphere(group, .1, [0, 2.79, .63], 0x4a342b, [1.35, .75, .36]);
        }
        if (config.equipment === 'handbag') {
            torus(group, .54, .045, [.78, .35, .08], 0xd7d4cf, [0, .2, -.55]);
            box(group, [.48, .58, .24], [.98, -.25, .22], 0xe5e1da, [0, 0, -.06]);
            box(group, [.34, .08, .27], [.98, .02, .22], 0xbcb8b1);
        }
        if (config.equipment === 'dog-varsity') {
            sphere(group, .26, [-1.45, -1.42, .2], 0xe5c58e, [1, .86, .88]);
            box(group, [.46, .62, .42], [-1.45, -1.77, .08], 0xe5c58e);
            addMesh(group, new THREE.ConeGeometry(.13, .35, 4), 0xc99f68, [-1.66, -1.28, .2], [0, 0, -.35]);
            addMesh(group, new THREE.ConeGeometry(.13, .35, 4), 0xc99f68, [-1.24, -1.28, .2], [0, 0, .35]);
            sphere(group, .045, [-1.54, -1.42, .43], 0x171719, [1, 1.15, .5]);
            sphere(group, .045, [-1.36, -1.42, .43], 0x171719, [1, 1.15, .5]);
            sphere(group, .06, [-1.45, -1.53, .46], 0x34241f, [1.2, .8, .5]);
            torus(group, .52, .025, [-.95, -.55, .2], 0xe8b5bd, [0, .5, -.65]);
            sphere(group, .34, [-.42, 2.75, -.05], config.hair, [1, .7, .9]);
            sphere(group, .34, [.42, 2.75, -.05], config.hair, [1, .7, .9]);
        }
        if (config.equipment === 'snow-dress') {
            addMesh(group, new THREE.ConeGeometry(1.02, .56, 32, 1, true), 0xf8f8f5, [0, -.38, 0], [0, 0, Math.PI]);
            [-1, 1].forEach((side) => {
                box(group, [.75, .64, .78], [side * .42, -1.63, .1], 0xf2f3f0);
                box(group, [.82, .2, .84], [side * .42, -1.94, .14], 0xdfe7e7);
            });
            torus(group, .42, .035, [0, 1.36, .36], 0xe7ecec, [Math.PI / 2, 0, 0]);
        }
        if (config.equipment === 'festive') {
            const red = 0xc62a25;
            const gold = 0xe0a839;
            cylinder(group, .61, .71, .66, [0, 3.01, -.02], 0x39231d);
            cylinder(group, .92, .92, .09, [0, 2.69, .02], red);
            [-1, 1].forEach((side) => {
                const x = side * .38;
                limbBetween(group, [x, 3.15, .05], [side * .68, 3.7, .02], .08, .08, red);
                limbBetween(group, [side * .56, 3.45, .03], [side * .78, 3.56, .02], .07, .07, red);
                limbBetween(group, [side * .64, 3.62, .03], [side * .8, 3.82, .02], .07, .07, red);
            });
            const hammerHandle = cylinder(group, .08, .08, 2.45, [-1.0, .7, .2], 0x332820, [0, 0, -.55]);
            hammerHandle.material.roughness = .45;
            box(group, [1.05, .75, .68], [-1.48, 1.62, .2], 0x6c3844, [0, 0, -.12]);
            const lightColors = [0xffd54a, 0x41d8cb, 0xf34f63];
            for (let index = 0; index < 7; index += 1) {
                sphere(group, .055, [-.62 + index * .2, .58 + Math.sin(index) * .1, .5], lightColors[index % 3]);
            }
            box(group, [.24, .22, .07], [0, 1.0, .49], gold);
        }
        if (config.equipment === 'cardboard-bot') {
            const cardboard = 0x9a6b36;
            const tape = 0x6c4b2c;
            box(group, [1.62, 1.5, 1.0], [0, .52, 0], cardboard);
            box(group, [1.58, 1.45, 1.38], [0, 2.14, 0], 0xa87740);
            box(group, [.26, .34, .08], [-.3, 2.25, .74], 0x1f1c19);
            box(group, [.26, .34, .08], [.3, 2.25, .74], 0x1f1c19);
            box(group, [.65, .08, .08], [0, 1.88, .75], 0x2c2520);
            [-1, 1].forEach((side) => {
                cylinder(group, .13, .13, .6, [side * .42, 3.15, 0], tape);
                sphere(group, .13, [side * .42, 3.48, 0], 0xe8e1d5);
                torus(group, .22, .06, [side * 1.08, .42, .04], 0x6d6d68, [Math.PI / 2, 0, 0]);
                torus(group, .22, .06, [side * .42, -1.03, .02], 0x6d6d68, [Math.PI / 2, 0, 0]);
            });
            box(group, [.7, .36, .08], [0, .53, .55], 0x6d4b2b);
            sphere(group, .09, [-.2, .53, .61], 0xd5473f, [1, 1, .5]);
            sphere(group, .09, [.2, .53, .61], 0x4c875a, [1, 1, .5]);
        }
        if (config.cap) {
            cylinder(group, .72, .76, .26, [0, 2.86, .01], config.cap);
            box(group, [.92, .1, .5], [0, 2.75, .52], config.cap, [-.08, 0, 0]);
        }
        if (config.hat) {
            cylinder(group, .76, .8, .34, [0, 2.91, 0], config.hat);
            cylinder(group, 1.02, 1.02, .09, [0, 2.72, .03], config.hat);
        }
        if (config.accessory === 'headphones') {
            addMesh(group, new THREE.TorusGeometry(.79, .09, 12, 32, Math.PI), config.accent, [0, 2.28, -.02]);
            box(group, [.2, .54, .34], [-.78, 2.23, 0], config.accent);
            box(group, [.2, .54, .34], [.78, 2.23, 0], config.accent);
        }
        if (config.accessory === 'basketball') {
            const ballPosition = [pose.leftHand[0], pose.leftHand[1] + .43, pose.leftHand[2] + .03];
            sphere(group, .43, ballPosition, 0xe96b25);
            torus(group, .32, .018, ballPosition, 0x291a15);
            torus(group, .32, .018, ballPosition, 0x291a15, [0, Math.PI / 2, 0]);
        }
        if (config.accessory === 'controller') {
            const controller = box(group, [1.08, .34, .2], [0, -.22, .66], 0x263244, [0, 0, 0]);
            sphere(controller, .055, [-.19, .04, .12], 0x24d7df);
            sphere(controller, .055, [.19, .04, .12], 0xff5a9e);
        }
        if ((config.accessory === 'chain' || config.accessory === 'glasses') && config.equipment !== 'steampunk') {
            limbBetween(group, [-.38, .96, .49], [0, .7, .5], .065, .065, 0xe2b34e);
            limbBetween(group, [0, .7, .5], [.38, .96, .49], .065, .065, 0xe2b34e);
        }
        if (config.accessory === 'bracelets') {
            torus(group, .18, .045, [pose.leftHand[0], pose.leftHand[1] + .2, pose.leftHand[2]], 0xffd24a, [Math.PI / 2, 0, 0]);
        }
    }

    function buildCharacter(style) {
        const config = STYLE_CONFIGS[style] || STYLE_CONFIGS.neon;
        const root = new THREE.Group();
        const body = new THREE.Group();
        root.add(body);

        const strong = config.build === 'strong';
        const widePants = config.outfit === 'wide-pants';
        box(body, [strong ? 1.7 : 1.42, 1.45, strong ? 1.0 : .86], [0, .55, 0], config.top);
        box(body, [1.46, .34, .92], [0, -.25, 0], config.accent);
        box(body, [widePants ? .7 : .58, 1.55, widePants ? .74 : .64], [-.42, -1.02, 0], config.bottom);
        box(body, [widePants ? .7 : .58, 1.55, widePants ? .74 : .64], [.42, -1.02, 0], config.bottom);
        box(body, [widePants ? .82 : .74, .42, 1.04], [-.42, -1.82, .17], config.shoes);
        box(body, [widePants ? .82 : .74, .42, 1.04], [.42, -1.82, .17], config.shoes);

        cylinder(body, .27, .3, .34, [0, 1.38, 0], config.skin);
        if (config.headShape === 'round') {
            sphere(body, .78, [0, 2.14, .03], config.skin, [1, 1.02, .94]);
        } else if (config.headShape === 'rounded') {
            roundedBox(body, [1.43, 1.38, 1.3], .28, [0, 2.14, 0], config.skin);
        } else {
            box(body, [1.43, 1.38, 1.3], [0, 2.14, 0], config.skin);
        }
        buildHair(body, config);
        if (config.equipment !== 'cardboard-bot') buildFace(body, config);
        const pose = buildArms(body, config);
        buildAccessories(body, config, pose);

        if (config.outfit === 'plaid') {
            [-.42, .42].forEach((x) => {
                box(body, [.08, 1.48, .05], [x - .12, -1.02, .35], 0xc8b9ac);
                box(body, [.08, 1.48, .05], [x + .14, -1.02, .35], 0x9e2730);
                [-1.38, -1.03, -.68].forEach((y) => box(body, [.56, .07, .05], [x, y, .35], 0x202126));
            });
        }
        if (config.equipment === 'dog-varsity') {
            box(body, [.63, 1.2, .08], [-.38, .58, .48], 0x3d2c27);
            box(body, [.63, 1.2, .08], [.38, .58, .48], 0xe8dfd0);
            box(body, [.28, .34, .09], [.35, .75, .53], 0x2e2622);
        }
        if (config.equipment !== 'cardboard-bot') {
            const chestStripe = box(body, [.85, .18, .06], [0, .7, .46], config.accent);
            chestStripe.material.roughness = .5;
        }
        root.scale.set(.9, .9, .9);
        return root;
    }

    function disposeViewer() {
        if (!currentViewer) return;
        cancelAnimationFrame(currentViewer.frame);
        currentViewer.observer.disconnect();
        currentViewer.root.traverse((object) => {
            if (object.geometry) object.geometry.dispose();
            if (object.material) object.material.dispose();
        });
        currentViewer.renderer.dispose();
        currentViewer = null;
    }

    function mount(container, style) {
        disposeViewer();
        if (!window.THREE) {
            container.textContent = 'Не удалось загрузить модуль 3D. Откройте приложение заново.';
            return;
        }
        container.replaceChildren();
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(34, 1, .1, 100);
        camera.position.set(0, .45, 9.5);
        const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true, powerPreference: 'low-power'});
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        scene.add(new THREE.HemisphereLight(0xffffff, 0x273046, 2.25));
        const key = new THREE.DirectionalLight(0xffffff, 3.2);
        key.position.set(4, 6, 7);
        key.castShadow = true;
        scene.add(key);
        const rim = new THREE.DirectionalLight(0x69dff0, 2.1);
        rim.position.set(-5, 3, -3);
        scene.add(rim);

        const root = buildCharacter(style);
        root.position.y = -.15;
        scene.add(root);
        const base = cylinder(scene, 1.75, 2.05, .22, [0, -2.05, 0], 0x283245);
        base.material.metalness = .35;

        let targetRotation = -.18;
        let dragging = false;
        let lastX = 0;
        renderer.domElement.addEventListener('pointerdown', (event) => {
            dragging = true;
            lastX = event.clientX;
            renderer.domElement.setPointerCapture(event.pointerId);
        });
        renderer.domElement.addEventListener('pointermove', (event) => {
            if (!dragging) return;
            targetRotation += (event.clientX - lastX) * .012;
            lastX = event.clientX;
        });
        renderer.domElement.addEventListener('pointerup', () => { dragging = false; });
        renderer.domElement.addEventListener('pointercancel', () => { dragging = false; });

        const resize = () => {
            const width = Math.max(container.clientWidth, 280);
            const height = Math.max(container.clientHeight, 300);
            renderer.setSize(width, height, false);
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
        };
        const observer = new ResizeObserver(resize);
        observer.observe(container);
        resize();

        const viewer = {renderer, root, observer, frame: 0};
        currentViewer = viewer;
        const animate = () => {
            if (currentViewer !== viewer) return;
            if (!dragging) targetRotation += .0022;
            root.rotation.y += (targetRotation - root.rotation.y) * .08;
            root.position.y = -.15 + Math.sin(performance.now() * .0015) * .025;
            renderer.render(scene, camera);
            viewer.frame = requestAnimationFrame(animate);
        };
        animate();
    }

    window.characterViewer = {mount, dispose: disposeViewer};
})();
