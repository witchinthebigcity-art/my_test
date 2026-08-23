(function () {
    const STYLE_CONFIGS = {
        neon: {skin: 0xf2b083, hair: 0x13bde1, hair2: 0x49f04d, top: 0xdfe7eb, accent: 0x39ed42, bottom: 0x151821, shoes: 0x35f04a, accessory: 'headphones', hairKind: 'spiky', headShape: 'square'},
        basket: {skin: 0xd99362, hair: 0x5a2e20, top: 0x16191b, accent: 0xff7425, bottom: 0x26282b, shoes: 0xf1f1ef, accessory: 'basketball', hairKind: 'spiky', headShape: 'square'},
        pixel: {skin: 0xf2af9b, hair: 0xff82c0, hair2: 0x35caef, top: 0xf7f8fa, accent: 0xff4aa6, bottom: 0x2c9ee8, shoes: 0xf7f8fa, accessory: 'controller', hairKind: 'long', cap: 0xf4f7fb, headShape: 'round'},
        'pink-wave': {skin: 0xf2b69b, hair: 0xffd2ba, hair2: 0xff8fc1, top: 0xff86bb, accent: 0xffffff, bottom: 0x42a9db, shoes: 0xff8fbd, accessory: 'none', hairKind: 'long', headShape: 'round', fashion: 'phone'},
        'white-street': {skin: 0xdca078, hair: 0x33251f, top: 0xf0f1f1, accent: 0xe43b35, bottom: 0x151719, shoes: 0xf2f1ec, accessory: 'glasses', hairKind: 'short', hat: 0xf0f0ed, headShape: 'square', fashion: 'smartwatch'},
        'aqua-pop': {skin: 0xf0aa83, hair: 0xff8db8, hair2: 0x36d8df, top: 0xff68a3, accent: 0x31d3da, bottom: 0x29cad2, shoes: 0x35d0d4, accessory: 'none', hairKind: 'long', headShape: 'round', fashion: 'airpods-print'},
        turbo: {skin: 0xe0ac82, hair: 0x38271f, top: 0x153f70, accent: 0xd9a83e, bottom: 0x202633, shoes: 0x8b5a2b, accessory: 'chain', hairKind: 'none', headShape: 'rounded', sleeve: 0xf2efe7, equipment: 'steampunk'},
        'cozy-plaid': {skin: 0xa96f50, hair: 0x151318, top: 0xf2f2f0, accent: 0xa52d36, bottom: 0x3b2228, shoes: 0xf3f1ed, accessory: 'earmuffs', hairKind: 'long', headShape: 'round', outfit: 'plaid'},
        'soft-blue': {skin: 0xdba881, hair: 0xe8c7b0, top: 0xf7f5f3, accent: 0xe9eef4, bottom: 0x8495a8, shoes: 0xf3f2ed, accessory: 'bows', hairKind: 'long', headShape: 'round', outfit: 'wide-pants'},
        'bronze-gent': {skin: 0xd4a078, hair: 0x4b2d1b, top: 0x8b531f, accent: 0xd49a3c, bottom: 0x6e421f, shoes: 0x9b662b, accessory: 'chain', hairKind: 'none', headShape: 'rounded', sleeve: 0x8b531f, equipment: 'bronze-suit'},
        'gym-hero': {skin: 0xb98667, hair: 0x111317, top: 0x111216, accent: 0xcb3e83, bottom: 0x16171a, shoes: 0xefefec, accessory: 'none', hairKind: 'swept', headShape: 'rounded', build: 'strong'},
        'capy-cozy': {skin: 0xe4b390, hair: 0x8a7168, top: 0xf6f3ef, accent: 0x8b6957, bottom: 0x6b5449, shoes: 0xf2efea, accessory: 'none', hairKind: 'long', headShape: 'round', equipment: 'capy-hat'},
        'city-white': {skin: 0xb67c5f, hair: 0x4b332b, top: 0xf5f2ed, accent: 0xd9d5cf, bottom: 0xc28e72, shoes: 0xf3f0ea, accessory: 'glasses', hairKind: 'long', headShape: 'round', equipment: 'handbag', fashion: 'phone'},
        'dog-varsity': {skin: 0xa86f50, hair: 0x40251f, top: 0x43322b, accent: 0xe9e1d2, bottom: 0x7f8588, shoes: 0xf1efea, accessory: 'none', hairKind: 'long', headShape: 'round', equipment: 'dog-varsity', fashion: 'smartwatch'},
        'snow-dream': {skin: 0xd6a27f, hair: 0xe7c9b7, top: 0xf7f8f6, accent: 0xdce7ea, bottom: 0xf5f6f3, shoes: 0xf1f2ef, accessory: 'none', hairKind: 'long', headShape: 'round', equipment: 'snow-dress', fashion: 'airpods'},
        'festive-forge': {skin: 0xe0aa8e, hair: 0x7b2a22, top: 0xd72e28, accent: 0xf1b83d, bottom: 0xb92222, shoes: 0x3b241d, accessory: 'none', hairKind: 'none', headShape: 'rounded', equipment: 'festive', fashion: 'smartwatch'},
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

    function box(group, size, position, color, rotation = null, options = {}) {
        return addMesh(group, new THREE.BoxGeometry(...size), color, position, rotation, null, options);
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

    function limbBetween3D(group, start, end, width, depth, color) {
        const startVector = new THREE.Vector3(...start);
        const endVector = new THREE.Vector3(...end);
        const direction = endVector.clone().sub(startVector);
        const length = direction.length() + .05;
        const mesh = addMesh(
            group,
            new THREE.BoxGeometry(width, length, depth),
            color,
            startVector.clone().add(endVector).multiplyScalar(.5).toArray(),
        );
        mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
        return mesh;
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
                if (config.fashion === 'airpods-print') {
                    sphere(group, .34, [-.27, 2.65, .65], color, [1.38, .52, .38]);
                    sphere(group, .34, [.27, 2.65, .65], config.hair2, [1.38, .52, .38]);
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

        if (config.seated) {
            leftElbow = [-1.06, .48, .08];
            rightElbow = [1.06, .48, .08];
            leftHand = [-.94, -.02, .5];
            rightHand = [.94, -.02, .5];
        }

        if (config.accessory === 'controller') {
            leftHand = [-.58, -.22, .55];
            rightHand = [.58, -.22, .55];
        } else if (config.accessory === 'basketball') {
            leftElbow = [-1.12, .82, .16];
            leftHand = [-1.24, 1.12, .42];
        } else if (config.equipment === 'dog-varsity') {
            leftElbow = [-1.08, .3, .12];
            leftHand = [-1.08, -.28, .34];
        } else if (config.fashion === 'phone' || config.fashion === 'fold-phone') {
            rightElbow = [1.13, .88, .12];
            rightHand = [.82, 1.34, .62];
        } else if (config.fashion === 'tablet') {
            leftElbow = [-1.05, .55, .12];
            rightElbow = [1.05, .55, .12];
            leftHand = [-.58, .52, .98];
            rightHand = [.58, .52, .98];
        } else if (config.fashion === 'laptop') {
            leftElbow = [-1.08, .5, .12];
            leftHand = [-.56, .78, .78];
        } else if (config.fashion === 'console') {
            leftElbow = [-1.08, .5, .12];
            rightElbow = [1.08, .5, .12];
            leftHand = [-.68, .56, .98];
            rightHand = [.68, .56, .98];
        } else if (config.fashion === 'camera' || config.fashion === 'camera-pro') {
            leftElbow = [-1.08, .52, .12];
            rightElbow = [1.08, .52, .12];
            leftHand = [-.58, .62, .97];
            rightHand = [.58, .62, .97];
        } else if (config.fashion === 'stylus' || config.fashion === 'projector') {
            rightElbow = [1.1, .62, .14];
            rightHand = [.9, .82, .68];
        } else if (config.equipment === 'festive') {
            rightElbow = [1.14, .55, .12];
            rightHand = [1.32, .08, .34];
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
            if (!config.shopHeadwear) {
                cylinder(group, .61, .72, .82, [0, 3.3, -.01], 0x2a211d);
                cylinder(group, .98, .98, .1, [0, 2.9, .02], bronze);
                box(group, [1.25, .16, .06], [0, 3.04, .53], gold);
                [-.31, .31].forEach((x) => {
                    torus(group, .18, .055, [x, 3.19, .6], gold);
                    cylinder(group, .13, .13, .055, [x, 3.19, .61], cyan, [Math.PI / 2, 0, 0]);
                    sphere(group, .035, [x - .035, 3.225, .66], 0xffffff);
                });
            }

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
            if (!config.shopHeadwear) {
                cylinder(group, .59, .68, .72, [0, 3.27, 0], bronze);
                cylinder(group, .94, .94, .09, [0, 2.91, .02], gold);
                [0, 1, 2].forEach((index) => {
                    sphere(group, .065, [-.24 + index * .24, 3.31, .58], 0x2c241e, [1, 1, .45]);
                });
            }
            box(group, [.35, .38, .08], [0, .85, .49], 0xf0e3ce);
            box(group, [.12, .55, .09], [0, .62, .5], 0x3a2d26);
            [-1, 1].forEach((side) => {
                box(group, [.62, .34, .64], [side * 1.02, .6, .03], gold, [0, 0, side * .15]);
                sphere(group, .07, [side * 1.02, .62, .39], 0x2b2928, [1, 1, .4]);
            });
        }
        if (config.equipment === 'capy-hat' && !config.shopHeadwear) {
            sphere(group, .72, [0, 3.2, -.02], 0x97725d, [1.08, .5, .93]);
            sphere(group, .2, [-.48, 3.42, -.02], 0x7d5b49, [.8, 1, .75]);
            sphere(group, .2, [.48, 3.42, -.02], 0x7d5b49, [.8, 1, .75]);
            sphere(group, .1, [0, 3.18, .63], 0x4a342b, [1.35, .75, .36]);
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
            limbBetween(group, pose.leftHand, [-1.18, -.78, .35], .035, .035, 0xe8b5bd);
            limbBetween(group, [-1.18, -.78, .35], [-1.45, -1.26, .34], .035, .035, 0xe8b5bd);
            box(group, [.4, .08, .3], [-1.45, -1.27, .22], 0xe8b5bd);
            sphere(group, .34, [-.42, 2.75, -.05], config.hair, [1, .7, .9]);
            sphere(group, .34, [.42, 2.75, -.05], config.hair, [1, .7, .9]);
        }
        if (config.equipment === 'snow-dress') {
            box(group, [1.0, .48, .78], [0, -.4, .02], 0xf8f8f5);
            cylinder(group, .78, 1.02, .56, [0, -.38, 0], 0xf8f8f5);
            [-1, 1].forEach((side) => {
                box(group, [.75, .64, .78], [side * .42, -1.63, .1], 0xf2f3f0);
                box(group, [.82, .2, .84], [side * .42, -1.94, .14], 0xdfe7e7);
            });
        }
        if (config.equipment === 'festive') {
            const red = 0xc62a25;
            const gold = 0xe0a839;
            if (!config.shopHeadwear) {
                cylinder(group, .61, .71, .66, [0, 3.25, -.02], 0x39231d);
                cylinder(group, .92, .92, .09, [0, 2.91, .02], red);
                [-1, 1].forEach((side) => {
                    const x = side * .38;
                    limbBetween(group, [x, 3.48, .05], [side * .68, 3.92, .02], .08, .08, red);
                    limbBetween(group, [side * .56, 3.72, .03], [side * .82, 3.8, .02], .07, .07, red);
                    limbBetween(group, [side * .65, 3.86, .03], [side * .82, 4.05, .02], .07, .07, red);
                });
            }
            const hammerEnd = [1.98, .74, .34];
            limbBetween(group, pose.rightHand, hammerEnd, .075, .075, 0x493126);
            box(group, [.62, .3, .34], [2.08, .84, .34], 0xb9c4ca, [0, 0, -.78], null, {roughness: .28, metalness: .66});
            box(group, [.19, .34, .39], [1.98, .74, .34], gold, [0, 0, -.78]);
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
        if (config.cap && !config.shopHeadwear) {
            cylinder(group, .72, .76, .26, [0, 3.06, .01], config.cap);
            box(group, [.92, .1, .5], [0, 2.91, .52], config.cap, [-.08, 0, 0]);
        }
        if (config.hat && !config.shopHeadwear) {
            cylinder(group, .76, .8, .34, [0, 3.1, 0], config.hat);
            cylinder(group, 1.02, 1.02, .09, [0, 2.91, .03], config.hat);
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
        if (config.fashion === 'phone' && !config.shopAccessory) {
            const phonePosition = [pose.rightHand[0] + .02, pose.rightHand[1] + .12, pose.rightHand[2] + .2];
            roundedBox(group, [.44, .76, .1], .09, phonePosition, 0x20242b);
            roundedBox(group, [.34, .6, .035], .06, [phonePosition[0], phonePosition[1], phonePosition[2] + .07], 0x63d8e5);
            sphere(group, .035, [phonePosition[0], phonePosition[1] - .31, phonePosition[2] + .1], 0xe8edf0, [1, 1, .4]);
        }
        if (config.fashion === 'smartwatch' && !config.shopAccessory) {
            const wrist = [pose.leftHand[0], pose.leftHand[1] + .23, pose.leftHand[2]];
            box(group, [.34, .16, .48], wrist, 0x20242b);
            roundedBox(group, [.28, .24, .08], .05, [wrist[0], wrist[1], wrist[2] + .27], 0x58d7d1);
        }
        if ((config.fashion === 'airpods' || config.fashion === 'airpods-print') && !config.shopAccessory) {
            [-1, 1].forEach((side) => {
                sphere(group, .075, [side * .76, 2.18, .22], 0xf8faf9, [.72, 1, .52]);
                box(group, [.055, .2, .055], [side * .76, 2.07, .22], 0xf8faf9, [0, 0, side * .08]);
            });
        }
        if (config.fashion === 'airpods-print') {
            box(group, [.82, .38, .045], [0, .63, .5], 0xf8f5ef);
            box(group, [.18, .24, .035], [-.24, .64, .535], 0xff5f9f, [0, 0, -.35]);
            box(group, [.18, .24, .035], [0, .64, .535], 0x43d5dd, [0, 0, .35]);
            box(group, [.18, .24, .035], [.24, .64, .535], 0xffd45b, [0, 0, -.35]);
        }
    }

    function addChestEmblem(group, color, gem = 0x57d8f0) {
        const crest = box(group, [.42, .48, .08], [0, .7, .62], color, [0, 0, Math.PI / 4], {roughness: .32, metalness: .6});
        crest.scale.set(.76, 1, 1);
        sphere(group, .09, [0, .7, .69], gem, [1, 1, .36]);
        [-1, 1].forEach((side) => limbBetween(group, [0, .7, .65], [side * .3, .93, .63], .035, .035, color));
    }

    function addCape(group, main, lining, trim, premium = false) {
        box(group, [1.78, 1.76, .14], [0, .23, -.54], lining, [0, 0, 0], {roughness: .88});
        box(group, [1.58, 1.68, .12], [0, .28, -.64], main, [0, 0, 0], {roughness: .5});
        box(group, [1.72, .16, .2], [0, 1.12, -.51], trim, null, {roughness: .3, metalness: .55});
        [-.66, -.44, -.22, 0, .22, .44, .66].forEach((x, index) => {
            sphere(group, premium ? .055 : .04, [x, -.5 + (index % 2) * .08, -.72], trim, [1, 1, .45]);
        });
        if (premium) {
            [-1, 1].forEach((side) => {
                sphere(group, .3, [side * .9, 1.04, -.22], trim, [1.2, .52, .8]);
                limbBetween(group, [side * .55, .82, -.72], [side * .15, -.2, -.73], .045, .045, trim);
            });
        }
    }

    function buildWearableOutfit(group, outfitId) {
        if (!outfitId) return;
        const gold = 0xe6b94d;
        const silver = 0xc7d5df;
        const pearl = 0xf4ead4;
        if (outfitId === 'outfit-viking') {
            addCape(group, 0x274b62, 0x152938, 0xb8964c, true);
            [-1, 1].forEach((side) => {
                sphere(group, .34, [side * .9, 1.08, -.08], 0xd7d0bf, [1.35, .66, .86]);
                box(group, [.35, .44, .1], [side * .43, .62, .55], 0x335f72, [0, 0, side * .12]);
            });
            addChestEmblem(group, gold, 0x63c4dc);
        } else if (outfitId === 'outfit-renaissance') {
            box(group, [1.5, 1.2, .14], [0, .56, .5], 0x702342, null, {roughness: .42});
            [-1, 1].forEach((side) => {
                box(group, [.62, 1.08, .08], [side * .38, .54, .59], side < 0 ? 0x7f2b4b : 0x5f1935, [0, 0, side * .04]);
                sphere(group, .3, [side * .89, 1.06, 0], 0xd5b469, [1.25, .6, .86]);
                limbBetween(group, [side * .58, 1.05, .62], [side * .18, .72, .64], .035, .035, gold);
            });
            [-.45, -.15, .15, .45].forEach((y) => sphere(group, .05, [0, .72 + y, .66], pearl, [1, 1, .42]));
        } else if (outfitId === 'outfit-victorian') {
            addCape(group, 0x172431, 0x401d34, gold, true);
            [-1, 1].forEach((side) => {
                box(group, [.72, 1.42, .13], [side * .38, .43, .55], 0x20384b, [0, 0, side * .035], {roughness: .35});
                box(group, [.09, 1.3, .04], [side * .06, .43, .66], gold, [0, 0, side * -.04], {metalness: .55});
                box(group, [.4, .14, .08], [side * .47, .94, .65], 0x822c45, [0, 0, side * .35]);
            });
            [1.0, .72, .44, .16].forEach((y) => sphere(group, .045, [0, y, .68], gold, [1, 1, .38]));
            limbBetween(group, [-.33, .85, .68], [.34, .58, .68], .035, .035, gold);
            addChestEmblem(group, gold, 0xb7375c);
        } else if (outfitId === 'outfit-neon') {
            box(group, [1.58, 1.26, .14], [0, .55, .5], 0x142a3a, null, {roughness: .34});
            [-1, 1].forEach((side) => {
                box(group, [.62, 1.1, .08], [side * .4, .56, .61], side < 0 ? 0x12637a : 0x522c82);
                limbBetween(group, [side * .68, 1.06, .66], [side * .22, .18, .66], .055, .045, side < 0 ? 0x42f1d5 : 0xff55c5);
            });
            box(group, [.48, .3, .08], [0, .68, .68], 0x12151b);
            box(group, [.32, .055, .04], [0, .68, .74], 0x7cfff2);
        } else if (outfitId === 'outfit-academy') {
            box(group, [1.34, 1.12, .12], [0, .58, .5], 0x263647);
            box(group, [.12, 1.0, .04], [0, .56, .61], 0xcab885);
            [-.32, -.1, .12, .34].forEach((y) => sphere(group, .04, [0, .67 + y, .66], gold));
            addChestEmblem(group, 0xcab885, 0x6bbfd2);
        } else if (outfitId === 'outfit-denim') {
            box(group, [1.55, 1.16, .14], [0, .56, .5], 0x376b8c);
            box(group, [1.48, .12, .08], [0, .05, .6], 0xd6c7a5);
            [[-.4, .78], [.38, .45], [-.28, .26]].forEach(([x, y], index) => {
                box(group, [.25, .19, .04], [x, y, .65], [0xe85d5d, 0xf2c14e, 0x61d4c9][index], [0, 0, index * .25]);
            });
        } else if (outfitId === 'outfit-varsity') {
            box(group, [1.58, 1.2, .14], [0, .56, .5], 0x304761);
            box(group, [.14, 1.08, .05], [0, .56, .63], pearl);
            [-1, 1].forEach((side) => box(group, [.7, .16, .08], [side * .38, 1.08, .62], 0xc64b4b));
            addChestEmblem(group, 0xf0d06b, 0xe65455);
        } else if (outfitId === 'outfit-cyber') {
            box(group, [1.56, 1.22, .15], [0, .56, .5], 0x111827, null, {roughness: .25});
            [[-.58, .98, -.18, .28], [.58, .8, .12, -.34], [-.42, .28, .28, -.1]].forEach(([x, y, dx, dy], index) => {
                limbBetween(group, [x, y, .67], [x + dx, y + dy, .67], .055, .04, index % 2 ? 0xff4bd8 : 0x36f4dd);
            });
            sphere(group, .11, [0, .64, .69], 0x69fff0, [1, 1, .35]);
        } else if (outfitId === 'outfit-samurai') {
            [-.42, 0, .42].forEach((x) => box(group, [.48, .98, .18], [x, .62, .51], 0x32475a, [0, 0, x * -.08], {metalness: .38}));
            [1.02, .74, .46, .18].forEach((y, index) => box(group, [1.62 - index * .1, .16, .16], [0, y, .62], index % 2 ? 0xa53036 : 0x1f2f40, null, {metalness: .35}));
            [-1, 1].forEach((side) => sphere(group, .34, [side * .92, 1.0, -.02], 0xa53036, [1.35, .52, .88]));
            addChestEmblem(group, gold, 0xc03d45);
        } else if (outfitId === 'outfit-astronomer') {
            addCape(group, 0x182d5a, 0x0d1734, silver, true);
            box(group, [1.5, 1.2, .13], [0, .56, .51], 0x203e74, null, {roughness: .38});
            const stars = [[-.5, .95], [.38, .9], [-.2, .56], [.48, .22], [-.48, .12]];
            stars.forEach(([x, y], index) => {
                sphere(group, index === 2 ? .075 : .045, [x, y, .68], index === 2 ? 0x7be8f6 : pearl, [1, 1, .36]);
                if (index) limbBetween(group, [stars[index - 1][0], stars[index - 1][1], .665], [x, y, .665], .018, .018, silver);
            });
        } else if (outfitId === 'outfit-baroque') {
            box(group, [1.55, 1.3, .15], [0, .52, .5], 0x5c245b, null, {roughness: .4});
            [-1, 1].forEach((side) => {
                box(group, [.52, 1.12, .07], [side * .4, .57, .62], side < 0 ? 0x6f3268 : 0x4b1b4a);
                for (let i = 0; i < 4; i += 1) torus(group, .11 + i * .015, .018, [side * (.18 + i * .11), .96 - i * .22, .7], gold);
                sphere(group, .3, [side * .9, 1.04, -.02], pearl, [1.35, .55, .86]);
            });
            [-.38, -.12, .14, .4].forEach((y) => sphere(group, .055, [0, .7 + y, .7], pearl, [1, 1, .38]));
        } else if (outfitId === 'outfit-celestial') {
            addCape(group, 0x101b4a, 0x4b2676, 0xc7e8ff, true);
            box(group, [1.56, 1.3, .16], [0, .53, .5], 0x17275f, null, {roughness: .25});
            [[-.5, 1.02], [.2, 1.08], [.5, .7], [-.1, .58], [-.48, .28], [.32, .15]].forEach(([x, y], index, stars) => {
                sphere(group, index % 3 === 0 ? .075 : .045, [x, y, .7], index % 3 === 0 ? 0x66e7ff : pearl, [1, 1, .3]);
                if (index) limbBetween(group, [stars[index - 1][0], stars[index - 1][1], .685], [x, y, .685], .022, .018, 0x9cdcff);
            });
            addChestEmblem(group, silver, 0x755cff);
        } else if (outfitId === 'outfit-imperial') {
            addCape(group, 0x741f31, 0x2d1020, gold, true);
            box(group, [1.58, 1.34, .16], [0, .5, .51], 0x8f2638, null, {roughness: .3});
            [-1, 1].forEach((side) => {
                sphere(group, .36, [side * .92, 1.03, -.03], gold, [1.35, .48, .82]);
                for (let i = 0; i < 3; i += 1) limbBetween(group, [side * (.58 - i * .1), 1.06, .68], [side * (.22 + i * .08), .2, .68], .035, .03, gold);
            });
            addChestEmblem(group, gold, 0xd23547);
        } else if (outfitId === 'outfit-dragon') {
            addCape(group, 0x351015, 0x0e0b0e, 0xd99a39, true);
            box(group, [1.58, 1.34, .18], [0, .5, .5], 0x49151c, null, {roughness: .3, metalness: .25});
            for (let row = 0; row < 4; row += 1) {
                for (let col = 0; col < 5; col += 1) {
                    const x = -.48 + col * .24 + (row % 2) * .1;
                    sphere(group, .13, [x, .94 - row * .25, .68], row % 2 ? 0x7a2025 : 0xa8322e, [1, .65, .28]);
                }
            }
            [-1, 1].forEach((side) => addMesh(group, new THREE.ConeGeometry(.16, .52, 6), gold, [side * .96, 1.3, -.08], [0, 0, side * -.55]));
            addChestEmblem(group, gold, 0xe6413f);
        } else if (outfitId === 'daily-victor-armor') {
            [-.45, 0, .45].forEach((x) => box(group, [.5, 1.18, .2], [x, .58, .51], x ? 0x65778d : 0x7f91a6, [0, 0, x * -.08], {roughness: .22, metalness: .7}));
            [-1, 1].forEach((side) => {
                sphere(group, .39, [side * .94, 1.02, -.04], gold, [1.32, .5, .86]);
                box(group, [.23, .62, .12], [side * .62, .45, .67], 0x94a5b4, [0, 0, side * .18], {metalness: .72});
            });
            addChestEmblem(group, gold, 0x54d8ff);
            [-.5, -.25, 0, .25, .5].forEach((x) => sphere(group, .05, [x, .08, .69], 0x53d7ff, [1, 1, .3]));
        } else if (outfitId === 'daily-victor-cape') {
            addCape(group, 0x6e1b55, 0x201038, gold, true);
            box(group, [1.52, 1.25, .15], [0, .54, .5], 0x55204e, null, {roughness: .3});
            [-1, 1].forEach((side) => {
                limbBetween(group, [side * .62, 1.03, .69], [side * .18, .18, .69], .04, .035, gold);
                sphere(group, .1, [side * .35, .66, .71], side < 0 ? 0x61e4ff : 0xff5fca, [1, 1, .32]);
            });
            addChestEmblem(group, gold, 0xb750ff);
        }
    }

    function buildShopAccessory(group, accessoryId, pose, config) {
        if (!accessoryId) return;
        const dark = 0x171d27;
        const cyan = 0x51e1ed;
        const gold = 0xe2b64b;
        if (accessoryId === 'gadget-phone' || accessoryId === 'gadget-fold-phone') {
            const position = [pose.rightHand[0] - .02, pose.rightHand[1] + .49, pose.rightHand[2] + .27];
            const premium = accessoryId === 'gadget-fold-phone';
            roundedBox(group, [premium ? .56 : .45, .78, .1], .08, position, premium ? 0x6040a4 : dark);
            roundedBox(group, [premium ? .46 : .35, .62, .025], .05, [position[0], position[1], position[2] + .067], premium ? 0x8ff4ff : 0x54cddd);
            if (premium) {
                box(group, [.035, .68, .025], [position[0], position[1], position[2] + .085], gold);
                sphere(group, .045, [position[0] + .18, position[1] + .27, position[2] + .09], 0xff69c8, [1, 1, .35]);
            }
        } else if (accessoryId === 'gadget-watch') {
            const wrist = [pose.leftHand[0], pose.leftHand[1] + .23, pose.leftHand[2]];
            box(group, [.34, .16, .46], wrist, dark);
            roundedBox(group, [.28, .24, .075], .05, [wrist[0], wrist[1], wrist[2] + .26], 0x58d7d1);
        } else if (accessoryId === 'gadget-tablet') {
            roundedBox(group, [1.16, .78, .1], .09, [0, .7, 1.02], dark);
            roundedBox(group, [.98, .62, .025], .06, [0, .7, 1.085], 0x61cadf);
            sphere(group, .04, [.48, .7, 1.11], pearlColor(), [1, 1, .34]);
        } else if (accessoryId === 'gadget-laptop') {
            box(group, [1.42, .12, .96], [0, .81, .9], 0x323b49, [-.12, 0, 0], {roughness: .25, metalness: .62});
            roundedBox(group, [1.42, .92, .1], .08, [0, 1.37, .68], 0x252e3d);
            roundedBox(group, [1.23, .72, .025], .055, [0, 1.38, .745], 0x4ed8e9);
            box(group, [.28, .28, .025], [0, 1.38, .77], 0xc9d7df, [0, 0, Math.PI / 4], {metalness: .5});
            sphere(group, .055, [0, 1.38, .79], 0x7c5cff, [1, 1, .32]);
        } else if (accessoryId === 'gadget-camera' || accessoryId === 'gadget-camera-pro') {
            const premium = accessoryId === 'gadget-camera-pro';
            roundedBox(group, [premium ? 1.02 : .82, .56, .34], .08, [0, .7, 1.02], premium ? 0x28374b : 0x252830);
            cylinder(group, premium ? .26 : .21, premium ? .23 : .19, .25, [0, .7, 1.24], premium ? gold : 0x68778b, [Math.PI / 2, 0, 0]);
            sphere(group, premium ? .16 : .13, [0, .7, 1.39], premium ? 0x62e7ff : 0x4d9ed1, [1, 1, .34]);
            if (premium) {
                torus(group, .36, .025, [0, .7, 1.46], 0x8ff5ff);
                sphere(group, .06, [.38, .89, 1.22], 0xff61c7, [1, 1, .35]);
            }
        } else if (accessoryId === 'gadget-stylus') {
            limbBetween(group, [pose.rightHand[0] + .03, pose.rightHand[1] + .2, pose.rightHand[2] + .16], [pose.rightHand[0] + .38, pose.rightHand[1] + .72, pose.rightHand[2] + .25], .055, .055, 0x6de8f0);
            sphere(group, .065, [pose.rightHand[0] + .4, pose.rightHand[1] + .75, pose.rightHand[2] + .26], 0xf3ca55, [1, 1, .5]);
        } else if (accessoryId === 'gadget-projector') {
            roundedBox(group, [.5, .28, .42], .06, [pose.rightHand[0], pose.rightHand[1] + .16, pose.rightHand[2] + .03], 0x303948);
            sphere(group, .1, [pose.rightHand[0], pose.rightHand[1] + .17, pose.rightHand[2] + .25], cyan, [1, 1, .3]);
            box(group, [.9, .56, .02], [pose.rightHand[0] - .3, pose.rightHand[1] + .75, pose.rightHand[2] + .28], 0x6ae4f0, [0, 0, -.12], {roughness: .12, metalness: .12});
        } else if (accessoryId === 'gadget-console') {
            roundedBox(group, [1.15, .42, .18], .12, [0, .61, 1.03], 0x313849);
            box(group, [.68, .32, .025], [0, .61, 1.14], 0x5bd2df);
            [-.43, .43].forEach((x, index) => sphere(group, .07, [x, .61, 1.17], index ? 0xff5f91 : 0x68ef9b, [1, 1, .35]));
        } else if (accessoryId === 'gadget-vr') {
            roundedBox(group, [1.22, .46, .2], .12, [0, 2.19, .77], 0x222a37);
            box(group, [1.02, .28, .035], [0, 2.19, .9], 0x62dfeb);
            torus(group, .8, .04, [0, 2.2, .05], 0x4b5970);
        } else if (accessoryId === 'gadget-glasses-classic' || accessoryId === 'gadget-glasses-fashion') {
            const fashion = accessoryId === 'gadget-glasses-fashion';
            const faceZ = config.headShape === 'round' ? .89 : .82;
            const frame = fashion ? 0x7ce4ef : 0x3a3534;
            [-1, 1].forEach((side) => {
                torus(group, fashion ? .25 : .22, fashion ? .04 : .025, [side * .3, 2.19, faceZ], frame);
                if (fashion) sphere(group, .055, [side * .3, 2.19, faceZ + .025], side < 0 ? 0xff79bc : 0x64dceb, [2.8, 2.8, .22]);
                limbBetween(group, [side * .48, 2.19, faceZ - .01], [side * .76, 2.16, faceZ - .12], .028, .028, frame);
            });
            box(group, [.16, .035, .035], [0, 2.19, faceZ], frame);
        } else if (accessoryId === 'gadget-sunglasses') {
            const faceZ = config.headShape === 'round' ? .89 : .82;
            [-1, 1].forEach((side) => {
                roundedBox(group, [.5, .31, .07], .07, [side * .3, 2.2, faceZ], 0x151923);
                box(group, [.44, .06, .025], [side * .3, 2.12, faceZ + .05], 0x6a4b9f);
                limbBetween(group, [side * .49, 2.2, faceZ - .01], [side * .76, 2.17, faceZ - .12], .035, .035, gold);
            });
            box(group, [.16, .045, .045], [0, 2.2, faceZ], gold);
        } else if (accessoryId === 'headwear-cap') {
            cylinder(group, .76, .82, .3, [0, 3.04, .01], 0x315d89);
            box(group, [.96, .1, .52], [0, 2.9, .55], 0x315d89, [-.08, 0, 0]);
            box(group, [.26, .26, .04], [0, 3.04, .74], 0xf2d15c, [0, 0, Math.PI / 4]);
        } else if (accessoryId === 'headwear-scarf') {
            const shell = addMesh(group, new THREE.SphereGeometry(.84, 32, 20, 0, Math.PI * 2, 0, Math.PI * .58), 0x8c4fa8, [0, 2.18, -.02], null, [1.03, 1.07, .96], {roughness: .42});
            shell.rotation.z = -.04;
            box(group, [.34, 1.0, .14], [-.62, 2.0, -.54], 0xa95fba, [0, 0, -.18]);
            box(group, [.28, .82, .13], [.54, 1.82, -.57], 0x6a3f8c, [0, 0, .28]);
            sphere(group, .12, [.58, 2.31, -.63], gold, [1, 1, .5]);
        } else if (accessoryId === 'headwear-fedora') {
            cylinder(group, .66, .76, .44, [0, 3.14, 0], 0x483229);
            cylinder(group, 1.02, 1.02, .08, [0, 2.93, .02], 0x3b2923);
            box(group, [1.26, .12, .06], [0, 3.02, .65], 0xb23e4e);
            sphere(group, .1, [.45, 3.06, .7], gold, [1, 1, .35]);
        } else if (accessoryId === 'headwear-beret') {
            sphere(group, .68, [-.12, 3.11, -.02], 0x8f294d, [1.14, .34, .86]);
            cylinder(group, .08, .06, .18, [-.17, 3.38, -.03], 0x542038, [0, 0, -.18]);
            box(group, [.08, .32, .035], [.34, 3.12, .56], silverColor(), [0, 0, .45], {metalness: .65});
        }
    }

    function pearlColor() {
        return 0xf2f6f7;
    }

    function silverColor() {
        return 0xcbd7df;
    }

    function buildInterior(group, interiorId) {
        if (!interiorId) return;
        const wood = 0x5b3826;
        const darkWood = 0x352218;
        const brass = 0xc5913d;
        const blue = 0x3b93b9;
        const x = 2.12;
        if (interiorId === 'interior-lamp') {
            cylinder(group, .34, .42, .12, [x, -1.82, -.15], brass);
            cylinder(group, .07, .09, 2.34, [x, -.62, -.15], brass);
            cylinder(group, .38, .72, .7, [x, .72, -.15], 0xd98d3d);
            sphere(group, .16, [x, .65, -.03], 0xffdf78, [1, 1, .5]);
        } else if (interiorId === 'interior-tea') {
            cylinder(group, .62, .7, .12, [x, -.62, -.08], wood);
            cylinder(group, .08, .12, 1.12, [x, -1.22, -.08], darkWood);
            sphere(group, .27, [x, -.3, -.02], 0xf1e7d4, [1.18, .86, 1]);
            torus(group, .19, .045, [x + .3, -.28, -.02], brass, [0, Math.PI / 2, 0]);
            cylinder(group, .08, .11, .14, [x - .36, -.42, .12], 0xf1e7d4);
        } else if (interiorId === 'interior-desk') {
            box(group, [1.08, .18, .72], [x, -.5, -.08], wood);
            [-1, 1].forEach((side) => box(group, [.12, 1.3, .12], [x + side * .42, -1.18, -.08], darkWood));
            box(group, [.82, .62, .08], [x, -.12, -.12], 0xc9a66b, [-.35, 0, 0]);
            [-.27, 0, .27].forEach((offset) => box(group, [.03, .42, .025], [x + offset, -.08, -.06], 0x6b4a30, [-.35, 0, 0]));
        } else if (interiorId === 'interior-globe') {
            cylinder(group, .32, .42, .12, [x, -1.82, -.1], brass);
            cylinder(group, .055, .08, 1.3, [x, -1.14, -.1], brass);
            sphere(group, .56, [x, -.18, -.08], blue, [1, 1, 1]);
            torus(group, .62, .035, [x, -.18, -.08], brass, [0, .25, 0]);
            torus(group, .53, .022, [x, -.18, -.08], 0x79c76b, [Math.PI / 2, 0, 0]);
        } else if (interiorId === 'interior-telescope') {
            [-1, 1].forEach((side) => limbBetween(group, [x, -.48, -.1], [x + side * .44, -1.82, -.12], .08, .08, brass));
            limbBetween(group, [x, -.48, -.1], [x, -1.84, .34], .08, .08, brass);
            const tube = cylinder(group, .18, .24, 1.26, [x, .18, -.06], 0x293a52, [0, 0, -.58]);
            tube.material.metalness = .5;
            cylinder(group, .27, .27, .18, [x - .36, .72, -.06], brass, [0, 0, -.58]);
            sphere(group, .12, [x - .43, .82, .02], 0x6be4ef, [1, 1, .35]);
        } else if (interiorId === 'interior-gramophone') {
            box(group, [.86, .72, .7], [x, -1.42, -.08], wood);
            cylinder(group, .08, .08, .72, [x, -.72, -.08], brass);
            addMesh(group, new THREE.ConeGeometry(.58, .92, 24, 1, true), brass, [x, -.1, -.08], [0, 0, Math.PI]);
            torus(group, .58, .045, [x, .36, -.08], 0xe0b45d, [Math.PI / 2, 0, 0]);
        } else if (interiorId === 'interior-arcade') {
            box(group, [1.05, 2.5, .82], [x, -.58, -.2], 0x22283d);
            roundedBox(group, [.82, .68, .04], .08, [x, .18, .24], 0x5ee1e8);
            box(group, [.9, .38, .68], [x, -.42, .06], 0x422a63, [-.28, 0, 0]);
            [-.2, .05, .28].forEach((offset, index) => sphere(group, .075, [x + offset, -.3, .43], [0xff5c8d, 0xffd15b, 0x54e4bd][index], [1, 1, .35]));
            box(group, [.58, .12, .06], [x, .82, .25], 0xff4db8);
        } else if (interiorId === 'interior-throne') {
            box(group, [1.92, .2, 1.05], [0, -.55, -.08], 0x5c2d35);
            box(group, [1.72, 2.25, .24], [0, .48, -.72], 0x4b2430);
            box(group, [1.48, 1.86, .1], [0, .52, -.57], 0x781f42);
            [-1, 1].forEach((side) => {
                box(group, [.22, 2.8, .28], [side * .86, -.02, -.68], darkWood);
                box(group, [.48, .16, 1.12], [side * 1.02, -.02, -.06], wood);
                box(group, [.16, 1.22, .18], [side * 1.02, -.72, -.06], darkWood);
                sphere(group, .18, [side * .86, 1.45, -.66], brass, [1, 1, .48]);
            });
            box(group, [.48, .48, .06], [0, .9, -.42], brass, [0, 0, Math.PI / 4], {metalness: .6});
            sphere(group, .1, [0, .9, -.37], 0x65dff1, [1, 1, .35]);
            [-.58, -.3, 0, .3, .58].forEach((offset, index) => sphere(group, .055, [offset, .82 + Math.abs(offset) * .28, -.42], index % 2 ? 0x65dff1 : 0xf0c458, [1, 1, .4]));
        }
    }

    function buildCharacter(style, equipped = []) {
        const config = {...(STYLE_CONFIGS[style] || STYLE_CONFIGS.neon)};
        const equippedOutfit = equipped.find((item) => item.startsWith('outfit-') || item.startsWith('daily-victor-'));
        const equippedAccessory = equipped.find((item) => item.startsWith('gadget-') || item.startsWith('headwear-'));
        const equippedInterior = equipped.find((item) => item.startsWith('interior-'));
        const accessoryPoses = {
            'gadget-phone': 'phone',
            'gadget-fold-phone': 'fold-phone',
            'gadget-tablet': 'tablet',
            'gadget-laptop': 'laptop',
            'gadget-console': 'console',
            'gadget-camera': 'camera',
            'gadget-camera-pro': 'camera-pro',
            'gadget-stylus': 'stylus',
            'gadget-projector': 'projector',
        };
        config.shopAccessory = equippedAccessory;
        config.shopHeadwear = Boolean(equippedAccessory?.startsWith('headwear-'));
        config.seated = equippedInterior === 'interior-throne';
        if (equippedAccessory && accessoryPoses[equippedAccessory]) config.fashion = accessoryPoses[equippedAccessory];
        const root = new THREE.Group();
        const body = new THREE.Group();
        root.add(body);

        const strong = config.build === 'strong';
        const widePants = config.outfit === 'wide-pants';
        box(body, [strong ? 1.7 : 1.42, 1.45, strong ? 1.0 : .86], [0, .55, 0], config.top);
        box(body, [1.46, .34, .92], [0, -.25, 0], config.accent);
        if (config.seated) {
            [-1, 1].forEach((side) => {
                const hip = [side * .42, -.38, 0];
                const knee = [side * .42, -.38, .82];
                const ankle = [side * .42, -1.28, .82];
                limbBetween3D(body, hip, knee, widePants ? .7 : .58, widePants ? .74 : .64, config.bottom);
                limbBetween3D(body, knee, ankle, widePants ? .7 : .58, widePants ? .74 : .64, config.bottom);
                sphere(body, .31, knee, config.bottom, [1, .92, .9]);
                box(body, [widePants ? .82 : .74, .42, 1.04], [side * .42, -1.56, 1.03], config.shoes);
            });
        } else {
            box(body, [widePants ? .7 : .58, 1.55, widePants ? .74 : .64], [-.42, -1.02, 0], config.bottom);
            box(body, [widePants ? .7 : .58, 1.55, widePants ? .74 : .64], [.42, -1.02, 0], config.bottom);
            box(body, [widePants ? .82 : .74, .42, 1.04], [-.42, -1.82, .17], config.shoes);
            box(body, [widePants ? .82 : .74, .42, 1.04], [.42, -1.82, .17], config.shoes);
        }

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
        buildWearableOutfit(body, equippedOutfit);
        buildShopAccessory(body, equippedAccessory, pose, config);
        buildInterior(root, equippedInterior);
        if (equippedInterior === 'interior-throne') {
            root.scale.set(.78, .78, .78);
        } else if (equippedInterior) {
            root.scale.set(.7, .7, .7);
            root.position.x = -.42;
        } else {
            root.scale.set(.9, .9, .9);
        }
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

    function mount(container, style, equipped = []) {
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

        const root = buildCharacter(style, equipped);
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
