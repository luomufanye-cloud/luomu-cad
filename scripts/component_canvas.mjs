// Native geometry recorder for the Luomu CAD component drawing functions.
// Coordinates and curve control points remain analytic through rigid transforms.
export class ComponentCanvas {
  constructor() {
    this.entities = []
    this.path = []
    this.cursor = null
    this.start = null
    this.matrix = [1, 0, 0, 1, 0, 0]
    this.stack = []
    this.dash = []
  }
  point(x, y) {
    const [a, b, c, d, e, f] = this.matrix
    return [a * x + c * y + e, b * x + d * y + f]
  }
  transform(a, b, c, d, e, f) {
    const [A, B, C, D, E, F] = this.matrix
    this.matrix = [A*a+C*b, B*a+D*b, A*c+C*d, B*c+D*d, A*e+C*f+E, B*e+D*f+F]
  }
  translate(x, y) { this.transform(1, 0, 0, 1, x, y) }
  rotate(angle) { this.transform(Math.cos(angle), Math.sin(angle), -Math.sin(angle), Math.cos(angle), 0, 0) }
  scale(x, y) { this.transform(x, 0, 0, y, 0, 0) }
  save() { this.stack.push({matrix: [...this.matrix], dash: [...this.dash]}) }
  restore() {
    const state = this.stack.pop()
    if (!state) throw new Error('Unbalanced canvas restore')
    this.matrix = state.matrix
    this.dash = state.dash
  }
  setLineDash(value) { this.dash = [...value] }
  beginPath() { this.path = []; this.cursor = null; this.start = null }
  moveTo(x, y) { this.cursor = this.point(x, y); this.start = this.cursor }
  lineTo(x, y) {
    const next = this.point(x, y)
    if (this.cursor && Math.hypot(next[0]-this.cursor[0], next[1]-this.cursor[1]) > 1e-9) {
      this.path.push({type: 'line', start: this.cursor, end: next})
    }
    this.cursor = next
  }
  closePath() {
    if (this.cursor && this.start && Math.hypot(this.cursor[0]-this.start[0], this.cursor[1]-this.start[1]) > 1e-9) {
      this.path.push({type: 'line', start: this.cursor, end: this.start})
    }
    this.cursor = this.start
  }
  rect(x, y, width, height) {
    this.moveTo(x, y); this.lineTo(x+width, y); this.lineTo(x+width, y+height)
    this.lineTo(x, y+height); this.closePath()
  }
  quadraticCurveTo(cx, cy, x, y) {
    if (!this.cursor) throw new Error('Curve requires a current point')
    const control = this.point(cx, cy), end = this.point(x, y)
    this.path.push({type: 'bezier', controls: [this.cursor, control, end]})
    this.cursor = end
  }
  bezierCurveTo(x1, y1, x2, y2, x, y) {
    if (!this.cursor) throw new Error('Curve requires a current point')
    const end = this.point(x, y)
    this.path.push({type: 'bezier', controls: [this.cursor, this.point(x1,y1), this.point(x2,y2), end]})
    this.cursor = end
  }
  arc(x, y, radius, start, end, anticlockwise=false) {
    this.ellipse(x, y, radius, radius, 0, start, end, anticlockwise)
  }
  ellipse(x, y, rx, ry, rotation, start, end, anticlockwise=false) {
    if (!(rx > 0 && ry > 0)) throw new Error('Positive curve radii required')
    const [a,b,c,d] = this.matrix
    const sx = Math.hypot(a,b), sy = Math.hypot(c,d)
    if (Math.abs(sx-sy) > 1e-8 || Math.abs(a*c+b*d) > 1e-8) throw new Error('Nonuniform curve transform unsupported')
    let sweep = end-start
    if (anticlockwise) {
      if (-sweep >= 2*Math.PI) sweep = -2*Math.PI
      else while (sweep > 0) sweep -= 2*Math.PI
    } else {
      if (sweep >= 2*Math.PI) sweep = 2*Math.PI
      else while (sweep < 0) sweep += 2*Math.PI
    }
    const local = angle => [x+rx*Math.cos(angle)*Math.cos(rotation)-ry*Math.sin(angle)*Math.sin(rotation),
      y+rx*Math.cos(angle)*Math.sin(rotation)+ry*Math.sin(angle)*Math.cos(rotation)]
    const first = local(start), last = local(start+sweep)
    if (this.cursor) this.lineTo(...first)
    else this.moveTo(...first)
    const reflected = a*d-b*c < 0
    const axisAngle = Math.atan2(b,a) + (reflected ? -rotation : rotation)
    this.path.push({type: 'ellipse_arc', center: this.point(x,y), rx: rx*sx, ry: ry*sx,
      rotation: axisAngle, start: reflected ? -start : start, sweep: reflected ? -sweep : sweep})
    this.cursor = this.point(...last)
  }
  stroke() { this.entities.push(...this.path.map(e=>({...e, dashed: this.dash.length > 0}))) }
  // CAD component outlines follow component stroked paths; fill colour is presentation metadata.
  fill() {}
  strokeRect(x,y,w,h) {
    const previous = {path:this.path, cursor:this.cursor, start:this.start}
    this.beginPath(); this.rect(x,y,w,h); this.stroke()
    Object.assign(this,previous)
  }
  fillRect(x,y,w,h) { this.strokeRect(x,y,w,h) }
  fillText(text,x,y) {
    this.entities.push({type:'text', text:String(text), point:this.point(x,y), font:this.font || '10px sans-serif'})
  }
  measureText(text) { return {width:String(text).length*10} }
  clip() { throw new Error('Clipped material paths require an explicit CAD representation') }
  drawImage() { throw new Error('Raster furniture images require a native CAD component') }
}
