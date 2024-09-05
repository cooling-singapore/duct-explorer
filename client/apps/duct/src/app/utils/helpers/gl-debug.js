// This debug functions for Webgl. 
// TODO: This file can be removed if it is not needed.

export function printUniforms(gl, program) {
  const numUniforms = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < numUniforms; ++i) {
    const info = gl.getActiveUniform(program, i);
    console.log(info);
  }
}