import {
  renderCoordinateTransformAt,
  requestRender,
} from '@arcgis/core/views/3d/externalRenderers';
import SpatialReference from '@arcgis/core/geometry/SpatialReference';
import { createProgram } from '../../../helpers/gl-helpers';
import { degree2meter, precision } from '../../../helpers/math-helpers';
import { mat4 } from 'gl-matrix/gl-matrix';

const mainVertexShader = ` #version 300 es
  precision highp float;
  in vec3 aPosition;
  in float aValue;

  uniform mat4 uMVP;
  uniform int uGridRowSize;
  uniform int uGridColSize;
  uniform int uGridPerRow;
  uniform int uSelectedID;
 
  out float value;
  out float selected;
  
  void main() {
      value = aValue;
      selected = float(uSelectedID == gl_InstanceID);
      
      vec3 pos = vec3(aPosition.x + float(gl_InstanceID % uGridPerRow * uGridRowSize),
      aPosition.y + float(gl_InstanceID / uGridPerRow * uGridColSize),
      aPosition.z);

      gl_Position = uMVP * vec4(pos, 1.0);
  }
`;

const mainFragmentShader = ` #version 300 es
  precision mediump float;

  in float value;
  in float selected;

  uniform sampler2D uColorRampSampler;

  out vec4 fragColor;
  
  void main() {
      if(value < 0.0) {
        discard;
      }
      vec4 color = vec4(1.0, 1.0, 1.0, 1.0) * selected + texture(uColorRampSampler, vec2(0.5, value)).rgba * (1.0-selected); 
   
      fragColor = color; 
  }
`;

const pickingVertexShader = ` #version 300 es
  precision highp float;

  in vec3 aPosition;
  in vec3 aColor;
  in float aValue;

  uniform mat4 uMVP;
  uniform int uGridRowSize;
  uniform int uGridColSize;
  uniform int uGridPerRow;

  out vec3 color;
  out float value;

  void main() {
      color = aColor;
      value = aValue;
      
      vec3 pos = vec3(aPosition.x + float(gl_InstanceID % uGridPerRow * uGridRowSize),
      aPosition.y + float(gl_InstanceID / uGridPerRow * uGridColSize),
      aPosition.z);

      gl_Position = uMVP * vec4(pos, 1.0);
  }
`;

const pickingFragmentShader = ` #version 300 es
  precision mediump float;
  in vec3 color;
  in float value;
  out vec4 fragColor;

  void main() {
    if(value < 0.0) {
      discard;
    }
    fragColor = vec4(color, 1.0);
  }
`;

export default class HeatmapRenderer {
  constructor(view, subtype) {
    this.view = view;
    this.subtype = subtype;
    this.visible = true;
    this.isInit = false;
    this.origin = [-1523583.0, 6191691.0, 149691.0];
    this.modelMatrix = new Float32Array(16);
    this.mvpMatrix = new Float32Array(16);
    this.tempMat4 = new Float32Array(16);
    this.pickingData = new Uint8Array(4);
    this.pickingEnable = false;
  }

  dispose() {
    if (this.gl) {
      this.gl.deleteTexture(this.colorRampTexture);
      this.gl.deleteBuffer(this.squadVbo);
      this.gl.deleteBuffer(this.pickingColorVbo);
      this.gl.deleteBuffer(this.dataVbo);
      this.gl.deleteFramebuffer(this.pickingFrameBuffer);
      this.visible = false;
    }
  }

  _genGridVbo(gl) {
    if (!this.data) {
      console.error('No data');
      return;
    }

    this.westSouth = degree2meter(this.data.area.west, this.data.area.south);
    this.eastNorth = degree2meter(this.data.area.east, this.data.area.north);

    const xAdjustment =
      1 -
      (0.188 * (103.55161 - this.data.area.west)) /
        (103.55161 - -90.3107227531639296);
    const yAdjustment =
      1 -
      (0.188 * (1.53428 - this.data.area.north)) /
        (1.53428 - 35.4107553234207444);

    this.gridRowSize =
      xAdjustment *
      Math.round(
        (this.eastNorth[0] - this.westSouth[0]) / this.data.grid.width
      );

    this.gridColSize =
      yAdjustment *
      Math.round(
        (this.eastNorth[1] - this.westSouth[1]) / this.data.grid.height
      );

    this.gridCount = this.data.grid.width * this.data.grid.height;

    this.vertices = new Float32Array([
      -0.5 * this.gridRowSize,
      0.5 * this.gridColSize,
      0.0,
      -0.5 * this.gridRowSize,
      -0.5 * this.gridColSize,
      0.0,
      0.5 * this.gridRowSize,
      -0.5 * this.gridColSize,
      0.0,
      0.5 * this.gridRowSize,
      -0.5 * this.gridColSize,
      0.0,
      0.5 * this.gridRowSize,
      0.5 * this.gridColSize,
      0.0,
      -0.5 * this.gridRowSize,
      0.5 * this.gridColSize,
      0.0,
    ]);

    this.verticesCount = this.vertices.length / 3;
    if (!this.squadVbo) {
      this.squadVbo = gl.createBuffer();
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.squadVbo);
    gl.bufferData(gl.ARRAY_BUFFER, this.vertices, gl.STATIC_DRAW);
  }

  _genDataVbo(gl) {
    if (!this.data) {
      console.error('No data');
      return;
    }

    const range =
      this.data.colors[this.data.colors.length - 1].value -
      this.data.colors[0].value;
    const dataAttributes = new Float32Array(
      this.data.data.map((x) =>
        x === this.data.no_data ? -1 : (x - this.data.colors[0].value) / range
      )
    );

    if (!this.dataVbo) {
      this.dataVbo = gl.createBuffer();
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.dataVbo);
    gl.bufferData(gl.ARRAY_BUFFER, dataAttributes, gl.STATIC_DRAW);
  }

  _genColorRampTexture(gl) {
    if (!this.data) {
      console.error('No data');
      return;
    }

    let colorChannel = this.data.colors[0].color.length;
    let colorRampData = new Uint8Array(this.data.colors.length * colorChannel);

    for (let i = 0; i < this.data.colors.length; i++) {
      let color = this.data.colors[i];
      for (let j = 0; j < colorChannel; j++) {
        colorRampData[(this.data.colors.length - i - 1) * colorChannel + j] =
          color.color[j];
      }
    }

    let width = 1;
    let height = this.data.colors.length;

    if (!this.colorRampTexture) {
      this.colorRampTexture = gl.createTexture();
    }

    gl.bindTexture(gl.TEXTURE_2D, this.colorRampTexture);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      width,
      height,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      colorRampData
    );

    // https://app.zenhub.com/workspaces/sec-digital-twin-lab-5f7e9787331a05002470dc62/issues/gh/cooling-singapore/digital-urban-climate-twin/714
    if (this.subtype === 'discrete') {
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    } else {
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    }

    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  }

  _genPickingColor(gl) {
    const pickingAttributes = new Float32Array(this.gridCount * 3);
    for (let i = 0; i < this.gridCount; i++) {
      pickingAttributes[i * 3] = ((i & 0x000000ff) >> 0) / 255.0;
      pickingAttributes[i * 3 + 1] = ((i & 0x0000ff00) >> 8) / 255.0;
      pickingAttributes[i * 3 + 2] = ((i & 0x00ff0000) >> 16) / 255.0;
    }

    if (!this.pickingColorVbo) {
      this.pickingColorVbo = gl.createBuffer();
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.pickingColorVbo);
    gl.bufferData(gl.ARRAY_BUFFER, pickingAttributes, gl.STATIC_DRAW);
  }

  _genPickingFBO(gl) {
    if (!this.targetTexture) {
      this.targetTexture = gl.createTexture();
    }
    gl.bindTexture(gl.TEXTURE_2D, this.targetTexture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    if (!this.depthBuffer) {
      this.depthBuffer = gl.createRenderbuffer();
    }
    gl.bindRenderbuffer(gl.RENDERBUFFER, this.depthBuffer);
    gl.bindTexture(gl.TEXTURE_2D, this.targetTexture);
    // TODO: handle rendering window resize events
    const level = 0;
    const internalFormat = gl.RGBA;
    const border = 0;
    const format = gl.RGBA;
    const type = gl.UNSIGNED_BYTE;
    const data = null;
    gl.texImage2D(
      gl.TEXTURE_2D,
      level,
      internalFormat,
      gl.canvas.width,
      gl.canvas.height,
      border,
      format,
      type,
      data
    );

    gl.renderbufferStorage(
      gl.RENDERBUFFER,
      gl.DEPTH_COMPONENT16,
      gl.canvas.width,
      gl.canvas.height
    );

    if (!this.pickingFrameBuffer) {
      this.pickingFrameBuffer = gl.createFramebuffer();
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickingFrameBuffer);

    gl.framebufferTexture2D(
      gl.FRAMEBUFFER,
      gl.COLOR_ATTACHMENT0,
      gl.TEXTURE_2D,
      this.targetTexture,
      level
    );
    gl.framebufferRenderbuffer(
      gl.FRAMEBUFFER,
      gl.DEPTH_ATTACHMENT,
      gl.RENDERBUFFER,
      this.depthBuffer
    );
  }

  _createProgram(gl) {
    this.mainProgram = createProgram(gl, mainVertexShader, mainFragmentShader);
    this.pickingProgram = createProgram(
      gl,
      pickingVertexShader,
      pickingFragmentShader
    );
  }

  _updateTransform(context) {
    mat4.identity(this.mvpMatrix);
    mat4.multiply(
      this.mvpMatrix,
      this.mvpMatrix,
      context.camera.projectionMatrix
    );
    mat4.multiply(
      this.mvpMatrix,
      this.mvpMatrix,
      mat4.translate(this.tempMat4, context.camera.viewMatrix, this.origin)
    );
    mat4.multiply(this.mvpMatrix, this.mvpMatrix, this.modelMatrix);
  }

  _updateStandardUniforms(gl, shader) {
    gl.uniformMatrix4fv(shader.uMVP, false, this.mvpMatrix);
    gl.uniform1i(shader.uGridRowSize, this.gridRowSize);
    gl.uniform1i(shader.uGridColSize, this.gridColSize);
    gl.uniform1i(shader.uGridPerRow, this.data.grid.width);
  }

  setData(data) {
    this.data = data;
    this.title = data.legend;

    this.updateGL = true;
    if (this.isInit) {
      requestRender(this.view);
    }
  }

  pickData(point) {
    if (!this.pickEnable) {
      return;
    }

    this.isPicking = true;
    this.mouseX = point.x;
    this.mouseY = point.y;
    requestRender(this.view);
  }

  enablePicking(enable) {
    this.pickingEnable = enable;
  }

  setup(context) {
    this.gl = context.gl;
    this._createProgram(context.gl);
    this.gl.pixelStorei(this.gl.UNPACK_FLIP_Y_WEBGL, true);
    this.isInit = true;
  }

  render(context) {
    const gl = context.gl;

    if (this.updateGL) {
      this._genGridVbo(context.gl);
      this._genDataVbo(context.gl);
      this._genColorRampTexture(context.gl);
      this._genPickingColor(context.gl);
      this._genPickingFBO(context.gl);

      this.modelMatrix = renderCoordinateTransformAt(
        this.view,
        [
          this.westSouth[0] + this.gridRowSize / 2,
          this.westSouth[1] + this.gridColSize / 2,
          1,
        ],
        SpatialReference.WebMercator,
        null
      );
      precision(this.origin, this.modelMatrix);

      this.updateGL = false;
      requestRender(this.view);
    }

    if (!this.visible) {
      return;
    }

    this._updateTransform(context);
    if (this.isPicking) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.pickingFrameBuffer);
      gl.enable(gl.CULL_FACE);
      gl.enable(gl.DEPTH_TEST);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

      gl.useProgram(this.pickingProgram.program);
      this._updateStandardUniforms(context.gl, this.pickingProgram);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.squadVbo);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 12, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.pickingColorVbo);
      gl.enableVertexAttribArray(1);
      gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 12, 0);
      gl.vertexAttribDivisor(1, 1);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.dataVbo);
      gl.enableVertexAttribArray(2);
      gl.vertexAttribPointer(2, 1, gl.FLOAT, false, 4, 0);
      gl.vertexAttribDivisor(2, 1);
      gl.drawArraysInstanced(
        gl.TRIANGLES,
        0,
        this.verticesCount,
        this.gridCount
      );

      // There is a pixel size miss matching between arcgis and webgl, 0.9 is the scale factor
      gl.readPixels(
        this.mouseX * 0.9,
        gl.canvas.height - this.mouseY * 0.9,
        1,
        1,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        this.pickingData
      );
      if (this.pickingData[3] === 0) {
        this.selectedID = -1;
      } else {
        this.selectedID =
          this.pickingData[0] +
          this.pickingData[1] * 256.0 +
          this.pickingData[2] * 256.0 * 256.0;
      }

      context.bindRenderTarget();
      this.isPicking = false;
    }

    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.CULL_FACE);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    gl.useProgram(this.mainProgram.program);
    this._updateStandardUniforms(context.gl, this.mainProgram);
    gl.uniform1i(
      this.mainProgram.uSelectedID,
      this.selectedID ? this.selectedID : -1
    );
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.colorRampTexture);
    gl.uniform1i(this.mainProgram.uColorRampSampler, 0);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.squadVbo);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 12, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.dataVbo);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 1, gl.FLOAT, false, 4, 0);
    gl.vertexAttribDivisor(1, 1);

    gl.drawArraysInstanced(gl.TRIANGLES, 0, this.verticesCount, this.gridCount);
    context.resetWebGLState();
  }
}
