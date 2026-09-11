// src/util/geometry.ts
function rotateDirection(d) {
  let ret = 0 /* None */;
  if (!(d & 4 /* Vertical */)) ret |= 4 /* Vertical */;
  if (d & 2 /* Right */) ret |= 1 /* Down */;
  if (d & 1 /* Down */) ret |= 2 /* Right */;
  return ret;
}
function directionFromPoint(r, p) {
  const x = p.x - r.x;
  const y = p.y - r.y;
  if (x < r.width / 2) {
    if (y < r.height / 2) {
      if (x > r.width * y / r.height) {
        return 4 /* Vertical */;
      } else {
        return 0 /* None */;
      }
    } else {
      if (x > r.width * y / r.height) {
        return 1 /* Down */ | 4 /* Vertical */;
      } else {
        return 1 /* Down */;
      }
    }
  } else {
    if (y < r.height / 2) {
      if (x < r.width * y / r.height) {
        return 2 /* Right */ | 4 /* Vertical */;
      } else {
        return 2 /* Right */;
      }
    } else {
      if (x < r.width * y / r.height) {
        return 1 /* Down */ | 2 /* Right */ | 4 /* Vertical */;
      } else {
        return 1 /* Down */ | 2 /* Right */;
      }
    }
  }
}

// src/util/stacklike.ts
var StackLike = class {
  getAtIndex(idx) {
    if (idx < 0) {
      return void 0;
    }
    let i = 0;
    for (const x of this) {
      if (idx == i) {
        return x;
      }
      i += 1;
    }
    return void 0;
  }
  multipush(values) {
    for (const value of values) {
      this.push(value);
    }
  }
  some(fn) {
    for (const x of this) {
      if (fn(x)) {
        return true;
      }
    }
    return false;
  }
  indexOf(fn) {
    let i = 0;
    for (const x of this) {
      if (fn(x)) {
        return i;
      }
      i += 1;
    }
    return -1;
  }
  find(fn) {
    for (const x of this) {
      if (fn(x)) {
        return x;
      }
    }
    return void 0;
  }
};

// src/util/queue.ts
var Node = class {
  constructor(value) {
    this.next = null;
    this.value = value;
  }
  append(node) {
    this.next = node;
    return this.next;
  }
};
var Queue = class extends StackLike {
  constructor() {
    super();
    this.head = null;
    this.tail = null;
    this.count = 0;
  }
  push(value) {
    if (this.head === null || this.tail === null) {
      this.head = new Node(value);
      this.tail = this.head;
    } else {
      this.tail = this.tail.append(new Node(value));
    }
    this.count += 1;
  }
  pop() {
    if (this.head === null) {
      return void 0;
    }
    const value = this.head.value;
    this.head = this.head.next;
    if (this.head === null) {
      this.tail = null;
    }
    this.count -= 1;
    return value;
  }
  peek() {
    return this.head?.value;
  }
  removeAtIndex(index) {
    if (index < 0 || index >= this.count) {
      return void 0;
    }
    let node = this.head;
    let prevNode = null;
    for (let i = 0; i < index; i += 1) {
      if (node === null) {
        return void 0;
      }
      prevNode = node;
      node = node.next;
    }
    if (node === null) return void 0;
    if (prevNode !== null) {
      prevNode.next = node.next;
      if (node === this.tail) {
        this.tail = prevNode;
      }
    } else {
      this.head = node.next;
    }
    this.count -= 1;
    return node.value;
  }
  get size() {
    return this.count;
  }
  get isEmpty() {
    return this.count === 0;
  }
  *[Symbol.iterator]() {
    let currNode = this.head;
    while (currNode !== null) {
      let ret = currNode.value;
      currNode = currNode.next;
      yield ret;
    }
  }
};

// src/util/stack.ts
var Node2 = class {
  constructor(value) {
    this.next = null;
    this.value = value;
  }
  append(node) {
    this.next = node;
    return this.next;
  }
};
var Stack = class extends StackLike {
  constructor() {
    super();
    this.head = null;
    this.count = 0;
  }
  push(value) {
    if (this.head === null) {
      this.head = new Node2(value);
    } else {
      this.head = this.head.append(new Node2(value));
    }
    this.count += 1;
  }
  pop() {
    if (this.head === null) {
      return void 0;
    }
    const value = this.head.value;
    this.head = this.head.next;
    this.count -= 1;
    return value;
  }
  peek() {
    return this.head?.value;
  }
  removeAtIndex(index) {
    if (index < 0 || index >= this.count) {
      return void 0;
    }
    let node = this.head;
    let prevNode = null;
    for (let i = 0; i < index; i += 1) {
      if (node === null) {
        return void 0;
      }
      prevNode = node;
      node = node.next;
    }
    if (node === null) return void 0;
    if (prevNode !== null) {
      prevNode.next = node.next;
    } else {
      this.head = node.next;
    }
    this.count -= 1;
    return node.value;
  }
  get size() {
    return this.count;
  }
  get isEmpty() {
    return this.count === 0;
  }
  *[Symbol.iterator]() {
    let currNode = this.head;
    while (currNode !== null) {
      let ret = currNode.value;
      currNode = currNode.next;
      yield ret;
    }
  }
};

// src/controller/event.ts
var Display = class _Display {
  static setWorkspace(workspace) {
    this.workspace = workspace;
  }
  constructor(desktop, activity, output) {
    this.desktop = desktop;
    this.activity = activity;
    this.output = output;
  }
  toString() {
    return `{"d":"${this.desktop.id}","a":"${this.activity}","o":"${this.output.name}"}`;
  }
  toSymbol() {
    return Symbol.for(this.toString());
  }
  equals(d) {
    return d && d.desktop === this.desktop && d.activity === this.activity && d.output === this.output;
  }
  static *generate(desktops, activities, outputs) {
    for (const desktop of desktops) {
      for (const activity of activities) {
        for (const output of outputs) {
          yield new _Display(desktop, activity, output);
        }
      }
    }
  }
  static *generateWindow(window) {
    const desktops = window.onAllDesktops ? this.workspace?.desktops ?? [] : window.desktops;
    for (const desktop of desktops) {
      for (const activity of window.activities) {
        yield new _Display(desktop, activity, window.output);
      }
    }
  }
};
function eventsAreSame(ev1, ev2) {
  if (ev1.t !== ev2.t) return false;
  for (const prop in ev1) {
    if (prop === "display") {
      if (ev1.display?.equals(ev2.display)) {
        continue;
      }
      return false;
    } else if (prop === "displays") {
      if (ev1.displays === void 0 || ev2.displays === void 0) {
        return false;
      }
      for (let i = 0; i < ev1.displays.length; i += 1) {
        if (!ev1.displays[i].equals(ev2.displays[i])) {
          return false;
        }
      }
      continue;
    }
    const val1 = ev1[prop];
    const val2 = ev2[prop];
    if (val1 !== val2) return false;
  }
  return true;
}
function simplifyEvents(oldEvents) {
  const newEvents = new Queue();
  for (const ev of oldEvents) {
    if (ev.t === "tileWindow" || ev.t === "untileWindow" || ev.t === "placeWindow") {
      const newEv = newEvents.find(
        (e) => e.t === "newWindow" && e.window === ev.window
      );
      if (newEv !== void 0 && newEv.t === "newWindow") {
        if (ev.t === "tileWindow") {
          newEv.forceTile = true;
          newEv.tile = void 0;
          newEv.direction = void 0;
        } else if (ev.t === "untileWindow") {
          newEv.forceTile = false;
          newEv.tile = void 0;
          newEv.direction = void 0;
        } else if (ev.t === "placeWindow") {
          newEv.forceTile = true;
          newEv.tile = ev.tile;
          newEv.direction = ev.direction;
        }
        continue;
      }
      const parallelIdx = newEvents.indexOf(
        (e) => (e.t === "tileWindow" || e.t === "untileWindow" || e.t === "placeWindow") && e.window === ev.window
      );
      if (parallelIdx != -1) {
        newEvents.removeAtIndex(parallelIdx);
      }
    }
    if (ev.t === "deleteWindow") {
      const newIdx = newEvents.indexOf(
        (e) => e.t === "newWindow" && e.window === ev.window
      );
      if (newIdx != -1) {
        newEvents.removeAtIndex(newIdx);
        continue;
      }
    }
    if (newEvents.some((e) => eventsAreSame(ev, e))) {
      continue;
    }
    if (ev.t == "changeEngine" && ev.engineSettings === void 0 && ev.engineType === void 0) {
      continue;
    }
    newEvents.push(ev);
  }
  return newEvents;
}
function simplifyPostEvents(oldEvents) {
  const newEvents = new Queue();
  for (const ev of oldEvents) {
    if (newEvents.some((e) => eventsAreSame(ev, e))) {
      continue;
    }
    newEvents.push(ev);
  }
  return newEvents;
}

// src/engine/engine.ts
var Window = class {
  constructor(id, name, minSize) {
    this.id = id;
    this.name = name;
    this.minSize = minSize;
  }
};
var Tile = class _Tile {
  constructor(parent) {
    this.children = [];
    this.layoutDirection = 1 /* Horizontal */;
    // relative size to other children of this tile
    this.size = 1;
    this.windows = [];
    this.parent = parent ?? null;
    if (this.parent == null) {
      return;
    }
  }
  // adds a child that will split perpendicularly to the parent. Returns the child
  addChild() {
    let splitDirection = 1 /* Horizontal */;
    if (this.layoutDirection == 1 /* Horizontal */) {
      splitDirection = 2 /* Vertical */;
    }
    const childTile = new _Tile(this);
    this.children.push(childTile);
    childTile.layoutDirection = splitDirection;
    return childTile;
  }
  // split a tile, aka add two children
  split() {
    this.addChild();
    this.addChild();
  }
  // removes a tile and all its children
  remove() {
    const parent = this.parent;
    if (parent == null) {
      return;
    }
    parent.children.splice(parent.children.indexOf(this), 1);
    this.children = [];
    this.windows = [];
  }
  // remove child tiles
  removeChildren() {
    for (const tile of this.children) {
      tile.remove();
    }
    this.children = [];
  }
  totalChildrenSize() {
    return this.children.reduce((s, t) => s + t.size, 0);
  }
  toJSON(includeWindows = false) {
    return {
      layoutDirection: this.layoutDirection,
      size: this.size,
      children: this.children.map((c) => c.toJSON()),
      windows: includeWindows ? this.windows.map((w) => w.id.toString()) : []
    };
  }
  static fromJSON(json, parent) {
    const tile = new _Tile(parent);
    if (parent != null) {
      parent.children.push(tile);
    }
    let obj;
    try {
      obj = typeof json === "string" ? JSON.parse(json) : json;
    } catch (_e) {
      return tile;
    }
    tile.layoutDirection = obj.layoutDirection;
    tile.size = obj.size;
    for (const child of obj.children) {
      _Tile.fromJSON(child, tile);
    }
    return tile;
  }
};
var BaseEngineSettings = class {
  getProps() {
    const ret = {};
    for (const key in this) {
      if (typeof this[key] !== "function") {
        ret[key] = this[key];
      }
    }
    return ret;
  }
  setProps(obj) {
    if (obj == null) return;
    for (const key in this) {
      if (obj.hasOwnProperty(key)) this[key] = obj[key];
    }
  }
};

// src/engine/layouts/btree.ts
var BTreeSettings = class extends BaseEngineSettings {
  constructor() {
    super(...arguments);
    this.swapInsertSide = false;
    this.rotateLayout = false;
    this.insertionStyle = 0 /* Shallow */;
    this.insertInActive = false;
  }
};
var Node3 = class _Node {
  constructor(parent) {
    this.parent = null;
    this.children = null;
    this.window = null;
    this.size = 1;
    this.destroyed = false;
    this.layoutDirectionRoot = 1 /* Horizontal */;
    if (parent) {
      this.parent = parent;
    }
  }
  get layoutDirection() {
    if (this.parent === null) {
      return this.layoutDirectionRoot;
    }
    if (this.parent.layoutDirection == 1 /* Horizontal */) {
      return 2 /* Vertical */;
    } else {
      return 1 /* Horizontal */;
    }
  }
  split(windowInheritor) {
    if (this.children !== null) {
      return;
    }
    this.children = [new _Node(this), new _Node(this)];
    this.children[windowInheritor].window = this.window;
    this.window = null;
  }
  // don't call this if a window exists in that tile
  // or I guess you could call it but it would untile the window
  destroy() {
    if (this.parent === null || this.parent.children === null) {
      return;
    }
    const sibling = this.parent.children[0] === this ? this.parent.children[1] : this.parent.children[0];
    if (sibling.window !== null) {
      this.parent.window = sibling.window;
    }
    this.parent.children = sibling.children === null ? null : [...sibling.children];
    for (const child of this.parent.children ?? []) {
      child.parent = this.parent;
    }
    this.destroyed = true;
    sibling.destroyed = true;
  }
};
var BTreeEngine = class {
  constructor() {
    this.settings = new BTreeSettings();
    this.root = new Node3();
    this.tileMap = /* @__PURE__ */ new Map();
    this.windowSet = /* @__PURE__ */ new Set();
  }
  getEngineSettings() {
    return this.settings.getProps();
  }
  setEngineSettings(settings) {
    this.settings.setProps(settings);
    this.root.layoutDirectionRoot = this.settings.rotateLayout ? 2 /* Vertical */ : 1 /* Horizontal */;
  }
  buildLayout() {
    const queue = new Queue();
    const rootTile = new Tile();
    this.tileMap.clear();
    queue.push([this.root, rootTile]);
    while (!queue.isEmpty) {
      const [node, tile] = queue.pop();
      this.tileMap.set(tile, node);
      if (node.window !== null) tile.windows.push(node.window);
      tile.size = node.size;
      tile.layoutDirection = node.layoutDirection;
      if (node.children !== null) {
        const [child1, child2] = node.children;
        const tile1 = tile.addChild();
        const tile2 = tile.addChild();
        queue.push([child1, tile1]);
        queue.push([child2, tile2]);
      }
    }
    return rootTile;
  }
  addWindow(window, tile, direction) {
    if (this.settings.insertInActive && tile !== void 0) {
      this.placeWindow(window, tile, direction);
      return;
    }
    if (this.windowSet.has(window)) return;
    this.windowSet.add(window);
    if (this.root.window === null && this.root.children === null) {
      this.root.window = window;
      return;
    }
    const queue = this.settings.insertionStyle === 0 /* Shallow */ ? new Queue() : new Stack();
    queue.push(this.root);
    let i = 0;
    while (!queue.isEmpty) {
      const node = queue.pop();
      let swapInsertSide = this.settings.swapInsertSide;
      if (this.settings.insertionStyle === 2 /* Spiral */) {
        if (i % 4 > 1) {
          swapInsertSide = !swapInsertSide;
        }
      }
      if (node.window !== null) {
        node.split(swapInsertSide ? 1 : 0);
        node.children[swapInsertSide ? 0 : 1].window = window;
        return;
      } else {
        if (node.children !== null) {
          const children = [...node.children];
          if (swapInsertSide) {
            children.reverse();
          }
          queue.multipush(children);
          i += 1;
        }
      }
    }
  }
  placeWindow(window, tile, direction) {
    if (this.windowSet.has(window)) {
      if (tile.windows.includes(window)) {
        return;
      }
      this.removeWindow(window);
    }
    this.windowSet.add(window);
    let node = this.tileMap.get(tile);
    console().debug(node);
    if (node == void 0) return;
    if (node.destroyed) {
      node = node.parent;
      if (node == null) return;
    }
    if (node.window === null) {
      node.window = window;
      return;
    }
    let insertPoint = this.settings.swapInsertSide ? 0 : 1;
    if (direction !== void 0) {
      insertPoint = node.layoutDirection === 1 /* Horizontal */ ? direction & 2 /* Right */ ? 1 : 0 : direction & 1 /* Down */ ? 1 : 0;
    }
    node.split(insertPoint === 0 ? 1 : 0);
    node.children[insertPoint].window = window;
  }
  windowActivated(window) {
    return false;
  }
  removeWindow(window) {
    if (!this.windowSet.has(window)) {
      return;
    }
    this.windowSet.delete(window);
    if (this.root.window === window) {
      this.root.window = null;
      return;
    }
    const queue = new Queue();
    queue.push(this.root);
    while (!queue.isEmpty) {
      const node = queue.pop();
      if (node.window === window) {
        node.destroy();
        return;
      } else {
        if (node.children !== null) {
          queue.multipush(node.children);
        }
      }
    }
  }
  updateTiles(_rootTile) {
    for (const [tile, node] of this.tileMap) {
      node.size = tile.size;
    }
  }
};

// src/engine/layouts/stackingcommon.ts
var WindowBox = class {
  constructor(window) {
    this.size = 1;
    this.window = window;
  }
};
var BoxIndex = class {
  constructor(boxes, index) {
    this.boxes = boxes;
    this.boxesLength = boxes.length;
    this.rawIndex = index;
  }
  get index() {
    let ret = this.rawIndex;
    if (ret < 0) {
      ret = 0;
    }
    if (ret >= this.boxes.length) {
      ret = this.boxes.length - 1;
    }
    return ret;
  }
  set index(idx) {
    this.rawIndex = idx;
  }
  get box() {
    return this.boxes[this.index];
  }
  set box(box) {
    this.boxes[this.index] = box;
  }
};

// src/engine/layouts/half.ts
var HalfEngineSettings = class extends BaseEngineSettings {
  constructor() {
    super(...arguments);
    this.middleSplit = 0.5;
    this.swapInsertSide = false;
    this.rotateLayout = false;
    this.insertInActive = false;
    this.keepMaster = false;
  }
};
var HalfEngine = class {
  constructor() {
    this.tileMap = /* @__PURE__ */ new Map();
    this.side1 = [];
    this.side2 = [];
    this.settings = new HalfEngineSettings();
  }
  getEngineSettings() {
    return this.settings.getProps();
  }
  setEngineSettings(settings) {
    const prevSwapSide = this.settings.swapInsertSide;
    this.settings.setProps(settings);
    if (this.settings.keepMaster && prevSwapSide === this.settings.swapInsertSide) {
      const [masterSide, otherSide] = this.settings.swapInsertSide ? [this.side2, this.side1] : [this.side1, this.side2];
      while (masterSide.length > 1) {
        const box = masterSide.splice(1, 1);
        otherSide.push(...box);
      }
    } else if (prevSwapSide !== this.settings.swapInsertSide) {
      const tmp = this.side1;
      this.side1 = this.side2;
      this.side2 = tmp;
    }
  }
  buildLayout() {
    const rootTile = new Tile();
    rootTile.layoutDirection = this.settings.rotateLayout ? 2 /* Vertical */ : 1 /* Horizontal */;
    this.tileMap.clear();
    if (this.side1.length == 0 && this.side2.length == 0) return rootTile;
    if (this.side1.length == 0 || this.side2.length == 0) {
      const dominantSide = this.side1.length == 0 ? this.side2 : this.side1;
      if (rootTile.layoutDirection == 1 /* Horizontal */) {
        rootTile.layoutDirection = 2 /* Vertical */;
      } else {
        rootTile.layoutDirection = 1 /* Horizontal */;
      }
      for (let i = 0; i < dominantSide.length; i += 1) {
        const box = dominantSide[i];
        const tile = rootTile.addChild();
        tile.windows.push(box.window);
        tile.size = box.size;
        this.tileMap.set(tile, new BoxIndex(dominantSide, i));
      }
      return rootTile;
    }
    for (const side of [this.side1, this.side2]) {
      const sideTile = rootTile.addChild();
      if (side === this.side1) {
        sideTile.size = this.settings.middleSplit * 2;
      } else {
        sideTile.size = (1 - this.settings.middleSplit) * 2;
      }
      if (side.length == 1) {
        sideTile.windows.push(side[0].window);
        this.tileMap.set(sideTile, new BoxIndex(side, 0));
      } else {
        for (let i = 0; i < side.length; i += 1) {
          const box = side[i];
          const tile = sideTile.addChild();
          tile.windows.push(box.window);
          tile.size = box.size;
          this.tileMap.set(tile, new BoxIndex(side, i));
        }
      }
    }
    return rootTile;
  }
  addWindow(window, tile, direction) {
    if (this.settings.insertInActive && tile !== void 0) {
      this.placeWindow(window, tile, direction);
      return;
    }
    if (!this.settings.swapInsertSide) {
      if (this.side1.length == 0) {
        this.side1.push(new WindowBox(window));
      } else {
        this.side2.push(new WindowBox(window));
      }
    } else {
      if (this.side2.length == 0) {
        this.side2.push(new WindowBox(window));
      } else {
        this.side1.push(new WindowBox(window));
      }
    }
  }
  removeWindow(window) {
    let [side, otherSide] = this.side1.some((x) => x.window == window) ? [this.side1, this.side2] : [this.side2, this.side1];
    let idx = side.findIndex((x) => x.window == window);
    if (idx == -1) {
      return;
    }
    side.splice(idx, 1);
    if (side.length == 0 && otherSide.length > 1) {
      side.push(otherSide.splice(0, 1)[0]);
    }
  }
  // default to inserting below
  placeWindow(window, tile, direction) {
    if (direction === void 0) {
      direction = 4 /* Vertical */;
    }
    if (this.settings.rotateLayout) {
      direction = rotateDirection(direction);
    }
    const target = this.tileMap.get(tile);
    if (target?.box === void 0) {
      this.addWindow(window);
      return;
    }
    if (target.box?.window === window) {
      return;
    }
    for (const [_tile, idx2] of this.tileMap) {
      const box = idx2.box;
      if (box?.window !== window) {
        continue;
      }
      if (idx2.boxes !== target.boxes) {
        this.removeWindow(box.window);
      } else {
        console().debug("swapping window in half");
        idx2.box = target.box;
        target.box = box;
        return;
      }
      break;
    }
    const newBox = new WindowBox(window);
    const [side, otherSide] = this.side1 === target.boxes ? [this.side1, this.side2] : [this.side2, this.side1];
    let idx = target.index;
    if (idx >= side.length) {
      idx = side.length - 1;
    }
    if (otherSide.length == 0) {
      if (side == this.side2 != ((direction & 2 /* Right */) != 0)) {
        otherSide.push(newBox);
      } else {
        otherSide.push(side.splice(0, 1)[0]);
        side.push(newBox);
      }
    } else {
      if (this.settings.keepMaster && (side == this.side1 && !this.settings.swapInsertSide || side == this.side2 && this.settings.swapInsertSide)) {
        const oldBox = side.pop();
        side.push(newBox);
        if (oldBox !== void 0) {
          otherSide.push(oldBox);
        }
      } else {
        if (direction & 1 /* Down */) {
          side.splice(idx + 1, 0, newBox);
        } else {
          side.splice(idx, 0, newBox);
        }
      }
    }
  }
  windowActivated(window) {
    return false;
  }
  updateTiles(rootTile) {
    if (rootTile.children.length == 2) {
      this.settings.middleSplit = rootTile.children[0].size / rootTile.totalChildrenSize();
    }
    for (const [tile, boxPointer] of this.tileMap) {
      const box = boxPointer.box;
      if (box === void 0) {
        continue;
      }
      if (boxPointer.boxes.length > 1) {
        box.size = tile.size;
      }
    }
  }
};

// src/engine/layouts/threecolumn.ts
var ThreeColumnEngineSettings = class extends BaseEngineSettings {
  constructor() {
    super(...arguments);
    this.side1Size = 0.25;
    this.side2Size = 0.25;
    this.swapInsertSide = false;
    this.rotateLayout = false;
  }
};
var ThreeColumnEngine = class {
  constructor() {
    // this is what I came up with
    // [WindowBox[], number] - Side and index of tile
    // boolean - true if center, false if invalid
    this.tileMap = /* @__PURE__ */ new Map();
    this.side1 = [];
    this.center = [];
    this.side2 = [];
    this.settings = new ThreeColumnEngineSettings();
  }
  getEngineSettings() {
    return this.settings.getProps();
  }
  setEngineSettings(settings) {
    this.settings.setProps(settings);
    if (this.settings.side1Size < 0.15) {
      this.settings.side1Size = 0.15;
    }
    if (this.settings.side2Size < 0.15) {
      this.settings.side2Size = 0.15;
    }
    if (this.settings.side1Size + this.settings.side2Size > 0.85) {
      const side1Ratio = this.settings.side1Size / (this.settings.side1Size + this.settings.side2Size);
      this.settings.side1Size = 0.85 * side1Ratio;
      this.settings.side2Size = 0.85 * (1 - side1Ratio);
    }
  }
  buildLayout() {
    const rootTile = new Tile();
    rootTile.layoutDirection = this.settings.rotateLayout ? 2 /* Vertical */ : 1 /* Horizontal */;
    this.tileMap.clear();
    if (this.side1.length == 0 && this.side2.length == 0) {
      if (this.center.length > 0) {
        rootTile.windows.push(this.center[0].window);
        this.tileMap.set(rootTile, new BoxIndex(this.center, 0));
      }
      return rootTile;
    }
    if (this.side1.length > 0) {
      const side1Tile = rootTile.addChild();
      side1Tile.size = this.settings.side1Size * 3;
      if (this.side1.length == 1) {
        side1Tile.windows.push(this.side1[0].window);
        this.tileMap.set(side1Tile, new BoxIndex(this.side1, 0));
      } else {
        for (let i = 0; i < this.side1.length; i += 1) {
          const box = this.side1[i];
          const tile = side1Tile.addChild();
          tile.windows.push(box.window);
          tile.size = box.size;
          this.tileMap.set(tile, new BoxIndex(this.side1, i));
        }
      }
    }
    const centerTile = rootTile.addChild();
    centerTile.size = 3;
    centerTile.size -= this.side1.length > 0 ? this.settings.side1Size * 3 : 0;
    centerTile.size -= this.side2.length > 0 ? this.settings.side2Size * 3 : 0;
    if (this.center.length > 0) {
      centerTile.windows.push(this.center[0].window);
      this.tileMap.set(centerTile, new BoxIndex(this.center, 0));
    }
    if (this.side2.length > 0) {
      const side2Tile = rootTile.addChild();
      side2Tile.size = this.settings.side2Size * 3;
      if (this.side2.length == 1) {
        side2Tile.windows.push(this.side2[0].window);
        this.tileMap.set(side2Tile, new BoxIndex(this.side2, 0));
      } else {
        for (let i = 0; i < this.side2.length; i += 1) {
          const box = this.side2[i];
          const tile = side2Tile.addChild();
          tile.windows.push(box.window);
          tile.size = box.size;
          this.tileMap.set(tile, new BoxIndex(this.side2, i));
        }
      }
    }
    return rootTile;
  }
  addWindow(window) {
    const box = new WindowBox(window);
    if (this.center.length == 0) {
      this.center.push(box);
      return;
    }
    const lengthDiff = this.side1.length - this.side2.length;
    if (lengthDiff == 0 && this.settings.swapInsertSide || lengthDiff > 0) {
      this.side2.push(box);
    } else {
      this.side1.push(box);
    }
  }
  removeWindow(window) {
    if (this.center[0]?.window == window) {
      this.center.pop();
      if (this.side1.length == 0 && this.side2.length == 0) return;
      const lengthDiff = this.side1.length - this.side2.length;
      if (lengthDiff == 0 && this.settings.swapInsertSide || lengthDiff < 0) {
        this.center.push(this.side2.splice(0, 1)[0]);
      } else {
        this.center.push(this.side1.splice(0, 1)[0]);
      }
      return;
    }
    let idx = this.side1.findIndex((x) => x.window == window);
    if (idx != -1) {
      this.side1.splice(idx, 1);
      if (this.side1.length == 0 && this.side2.length > 1) {
        this.side1.push(this.side2.splice(0, 1)[0]);
      }
      return;
    }
    idx = this.side2.findIndex((x) => x.window == window);
    if (idx == -1) return;
    this.side2.splice(idx, 1);
    if (this.side2.length == 0 && this.side1.length > 1) {
      this.side2.push(this.side1.splice(0, 1)[0]);
    }
  }
  // default to inserting below
  placeWindow(window, tile, direction) {
    if (this.center === null) {
      this.addWindow(window);
      return;
    }
    if (direction === void 0) {
      direction = 4 /* Vertical */;
    }
    if (this.settings.rotateLayout) {
      direction = rotateDirection(direction);
    }
    const target = this.tileMap.get(tile);
    if (target?.box === void 0) {
      this.addWindow(window);
      return;
    }
    if (target.box?.window === window) {
      return;
    }
    for (const [_tile, idx] of this.tileMap) {
      const box = idx.box;
      if (box?.window !== window) {
        continue;
      }
      if (idx.boxes !== target.boxes) {
        this.removeWindow(box.window);
      } else {
        idx.box = target.box;
        target.box = box;
        return;
      }
      break;
    }
    const newBox = new WindowBox(window);
    if (target.boxes === this.center) {
      if (!(direction & 2 /* Right */) && this.side1.length == 0) {
        this.side1.push(newBox);
      } else if (direction & 2 /* Right */ && this.side2.length == 0) {
        this.side2.push(newBox);
      } else {
        const oldCenter = this.center[0];
        this.center.splice(0, 1, newBox);
        this.addWindow(oldCenter.window);
      }
    } else {
      let idx = target.index;
      if (idx >= target.boxes.length) {
        idx = target.boxes.length - 1;
      }
      if (direction & 1 /* Down */) {
        idx += 1;
      }
      target.boxes.splice(idx, 0, newBox);
    }
  }
  windowActivated(window) {
    return false;
  }
  updateTiles(rootTile) {
    if (this.side1.length > 0) {
      this.settings.side1Size = rootTile.children[0].size / rootTile.totalChildrenSize();
      if (this.side2.length > 0) {
        this.settings.side2Size = rootTile.children[2].size / rootTile.totalChildrenSize();
      }
    } else if (this.side2.length > 0) {
      this.settings.side2Size = rootTile.children[1].size / rootTile.totalChildrenSize();
    }
    for (const [tile, idx] of this.tileMap) {
      if (idx.boxes === this.center) {
        continue;
      }
      const box = idx.box;
      if (box === void 0) {
        continue;
      }
      if (idx.boxes.length > 1) {
        box.size = tile.size;
      }
    }
  }
};

// src/engine/layouts/pillars.ts
var Pillar = class {
  constructor() {
    this.boxes = [];
    this.size = 1;
  }
};
var PillarEngineSettings = class extends BaseEngineSettings {
  constructor() {
    super(...arguments);
    this.pillarCount = 3;
    this.swapInsertSide = false;
    this.rotateLayout = false;
    this.insertInActive = false;
    this.insertionStyle = 0 /* Rows */;
  }
};
var PillarEngine = class {
  constructor() {
    // first number is pillar, second is index within pillar
    this.tileMap = /* @__PURE__ */ new Map();
    this.pillars = [];
    this.settings = new PillarEngineSettings();
  }
  getEngineSettings() {
    return this.settings.getProps();
  }
  setEngineSettings(settings) {
    this.settings.setProps(settings);
    if (this.settings.pillarCount < 1) {
      this.settings.pillarCount = 1;
    }
    if (this.pillars.length == 0) return;
    while (this.pillars.length > this.settings.pillarCount) {
      const pillar = this.pillars.pop();
      if (pillar !== void 0) {
        for (const box of pillar.boxes) {
          this.addWindow(box.window);
        }
      }
    }
    while (this.pillars.length < this.settings.pillarCount) {
      const pillar = this.getPillarWithMost(this.pillars.length - 1);
      if (pillar.boxes.length <= 1) break;
      const window = pillar.boxes[pillar.boxes.length - 1].window;
      this.removeWindow(window);
      this.addWindow(window);
    }
  }
  buildLayout() {
    const rootTile = new Tile();
    rootTile.layoutDirection = this.settings.rotateLayout ? 2 /* Vertical */ : 1 /* Horizontal */;
    this.tileMap.clear();
    for (const pillar of this.pillars) {
      let pillarTile = rootTile;
      if (this.pillars.length > 1) {
        pillarTile = rootTile.addChild();
        pillarTile.size = pillar.size;
      }
      if (pillar.boxes.length == 1) {
        pillarTile.windows.push(pillar.boxes[0].window);
        this.tileMap.set(pillarTile, new BoxIndex(pillar.boxes, 0));
      } else {
        for (let i = 0; i < pillar.boxes.length; i += 1) {
          const box = pillar.boxes[i];
          const tile = pillarTile.addChild();
          tile.windows.push(box.window);
          tile.size = box.size;
          this.tileMap.set(tile, new BoxIndex(pillar.boxes, i));
        }
      }
    }
    return rootTile;
  }
  addWindow(window, tile, direction) {
    if (tile !== void 0 && this.settings.insertInActive) {
      this.placeWindow(window, tile, direction);
      return;
    }
    const windowBox = new WindowBox(window);
    if (this.pillars.length < this.settings.pillarCount) {
      const pillar = new Pillar();
      pillar.boxes.push(windowBox);
      if (this.settings.swapInsertSide) {
        this.pillars.splice(0, 0, pillar);
      } else {
        this.pillars.push(pillar);
      }
      return;
    }
    let pillarIdx = 0;
    let rowIdx = 0;
    const style = this.settings.insertionStyle;
    while (true) {
      const pillar = this.settings.swapInsertSide ? this.pillars[this.pillars.length - pillarIdx - 1] : this.pillars[pillarIdx];
      if (pillar.boxes.length <= rowIdx) {
        if (style & 2 /* RowsUp */) {
          pillar.boxes.splice(0, 0, windowBox);
        } else {
          pillar.boxes.push(windowBox);
        }
        return;
      }
      if (style & 1 /* Snake */ && rowIdx % 2 != 0) {
        pillarIdx -= 1;
      } else {
        pillarIdx += 1;
      }
      if (pillarIdx >= this.pillars.length || pillarIdx < 0) {
        rowIdx += 1;
        if (style & 1 /* Snake */ && rowIdx % 2 != 0) {
          pillarIdx = this.pillars.length - 1;
        } else {
          pillarIdx = 0;
        }
      }
    }
  }
  removeWindow(window) {
    const pillarIdx = this.pillars.findIndex(
      (p) => p.boxes.some((b) => b.window == window)
    );
    if (pillarIdx === -1) return;
    const pillar = this.pillars[pillarIdx];
    const boxIdx = pillar.boxes.findIndex((b) => b.window == window);
    if (boxIdx === -1) return;
    pillar.boxes.splice(boxIdx, 1);
    if (pillar.boxes.length == 0) {
      const pillarWithMost = this.getPillarWithMost(boxIdx);
      if (pillarWithMost.boxes.length > 1) {
        pillar.boxes.push(pillarWithMost.boxes.pop());
      } else {
        this.pillars.splice(pillarIdx, 1);
      }
    }
  }
  placeWindow(window, tile, direction) {
    if (direction === void 0) {
      direction = 0 /* None */;
    }
    if (this.settings.rotateLayout) {
      direction = rotateDirection(direction);
    }
    if (tile.windows.includes(window)) {
      return;
    }
    const target = this.tileMap.get(tile);
    if (target?.box === void 0) {
      this.addWindow(window);
      return;
    }
    for (const [_tile, idx2] of this.tileMap) {
      const box = idx2.box;
      if (box?.window !== window) {
        continue;
      }
      if (idx2.boxes !== target.boxes) {
        this.removeWindow(box.window);
      } else {
        idx2.box = target.box;
        target.box = box;
        return;
      }
      break;
    }
    const newBox = new WindowBox(window);
    let pillarIdx = this.pillars.findIndex((x) => x.boxes === target.boxes);
    if (pillarIdx >= this.pillars.length) {
      pillarIdx = this.pillars.length - 1;
    } else if (pillarIdx < 0) {
      pillarIdx = 0;
    }
    if (this.pillars.length < this.settings.pillarCount) {
      let idx2 = pillarIdx;
      if (direction & 2 /* Right */) {
        idx2 += 1;
      }
      const pillar2 = new Pillar();
      pillar2.boxes.push(newBox);
      this.pillars.splice(idx2, 0, pillar2);
      return;
    }
    const pillar = this.pillars[pillarIdx];
    let boxIdx = target.index;
    if (boxIdx >= pillar.boxes.length) {
      boxIdx = pillar.boxes.length - 1;
    }
    let idx = boxIdx;
    if (direction & 1 /* Down */) {
      idx += 1;
    }
    pillar.boxes.splice(idx, 0, newBox);
  }
  windowActivated(window) {
    return false;
  }
  updateTiles(rootTile) {
    if (rootTile.children.length == 0 || rootTile.children.length == 1 || this.pillars.length == 0) {
      return;
    }
    for (let i = 0; i < rootTile.children.length; i += 1) {
      let subTile = rootTile;
      const pillar = this.pillars[i];
      if (this.pillars.length > 1) {
        subTile = rootTile.children[i];
        pillar.size = subTile.size;
      } else {
        i += rootTile.children.length;
      }
      for (let j = 0; j < subTile.children.length; j += 1) {
        pillar.boxes[j].size = subTile.children[j].size;
      }
    }
  }
  // get pillar with most children
  // use refIdx as a reference, tries to return the pillar closest to the index with the most
  getPillarWithMost(refIdx) {
    return this.pillars.reduce(
      ([r, ri], p, i) => {
        if (p.boxes.length > r.boxes.length) {
          return [p, i];
        } else if (p.boxes.length == r.boxes.length && refIdx !== void 0 && Math.abs(i - refIdx) >= ri - refIdx) {
          return [p, i];
        }
        return [r, ri];
      },
      [this.pillars[0], 0]
    )[0];
  }
};

// src/engine/layouts/pager.ts
var PagerSettings = class extends BaseEngineSettings {
  constructor() {
    super(...arguments);
    this.pageWidth = 0.15;
    this.swapInsertSide = false;
    this.rotateLayout = false;
  }
};
var floatingPointFix = 1e-5;
var PagerEngine = class {
  constructor() {
    this.settings = new PagerSettings();
    this.pageWidth = this.settings.pageWidth + floatingPointFix;
    this.windows = [];
    this.activeWindowIdx = -1;
  }
  getEngineSettings() {
    return this.settings.getProps();
  }
  setEngineSettings(settings) {
    this.settings.setProps(settings);
    this.pageWidth = this.settings.pageWidth + floatingPointFix;
  }
  buildLayout() {
    const rootTile = new Tile();
    if (this.settings.rotateLayout) {
      rootTile.layoutDirection = 2 /* Vertical */;
    } else {
      rootTile.layoutDirection = 1 /* Horizontal */;
    }
    const len = this.windows.length;
    if (len == 0) {
      return rootTile;
    }
    if (len == 1) {
      rootTile.windows.push(this.windows[0]);
      return rootTile;
    }
    for (let i = 0; i < len; i += 1) {
      const tile = rootTile.addChild();
      tile.windows.push(this.windows[i]);
      if (i == this.activeWindowIdx) {
        tile.size = (1 - this.pageWidth * (len - 1)) * len;
      } else {
        tile.size = this.pageWidth * len;
      }
    }
    return rootTile;
  }
  addWindow(window) {
    if (!this.settings.swapInsertSide) {
      this.windows.push(window);
    } else {
      this.windows.splice(0, 0, window);
    }
  }
  placeWindow(window, tile, direction) {
    if (direction === void 0) {
      direction = 0 /* None */;
    }
    if (this.settings.rotateLayout) {
      direction = rotateDirection(direction);
    }
    if (tile.windows.length == 0 || tile.windows.includes(window)) {
      return;
    }
    if (this.windows.includes(window)) {
      this.removeWindow(window);
    }
    let idx = this.windows.findIndex((w) => tile.windows.includes(w));
    if (direction & 2 /* Right */) {
      idx += 1;
    }
    this.windows.splice(idx, 0, window);
  }
  windowActivated(window) {
    const idx = this.windows.indexOf(window);
    if (idx === this.activeWindowIdx || idx === -1) {
      return false;
    }
    this.activeWindowIdx = idx;
    return true;
  }
  removeWindow(window) {
    const idx = this.windows.indexOf(window);
    if (idx == -1) {
      return;
    }
    if (this.activeWindowIdx == idx) {
      this.activeWindowIdx = -1;
    }
    this.windows.splice(idx, 1);
  }
  updateTiles(rootTile) {
  }
};

// src/engine/layouts/kwin.ts
var KwinEngine = class {
  constructor() {
    this.rootTile = new Tile();
    this.windowTiles = /* @__PURE__ */ new Map();
  }
  getEngineSettings() {
    return {
      tiles: this.rootTile.toJSON()
    };
  }
  setEngineSettings(settings) {
    const tiles = settings.tiles;
    if (tiles == void 0) {
      return;
    }
    this.rootTile = Tile.fromJSON(tiles);
  }
  buildLayout() {
    return this.rootTile;
  }
  addWindow(_window, _tile, _direction) {
    return;
  }
  removeWindow(window) {
    const tile = this.windowTiles.get(window);
    this.windowTiles.delete(window);
    if (tile === void 0) {
      return;
    }
    tile.windows.splice(tile.windows.indexOf(window), 1);
  }
  placeWindow(window, tile, _direction) {
    if (this.windowTiles.has(window)) {
      const oldTile = this.windowTiles.get(window);
      oldTile.windows.splice(oldTile.windows.indexOf(window), 1);
    }
    if (!tile.windows.includes(window)) {
      tile.windows.push(window);
    }
    this.windowTiles.set(window, tile);
  }
  windowActivated(_window) {
    return false;
  }
  updateTiles(rootTile) {
    this.rootTile = rootTile;
  }
};

// src/engine/index.ts
var TilingEngine = class {
  constructor(type, settings) {
    this.engineType = type;
    switch (type) {
      case 0 /* BTree */:
        this.engine = new BTreeEngine();
        break;
      case 1 /* Half */:
        this.engine = new HalfEngine();
        break;
      case 2 /* ThreeColumn */:
        this.engine = new ThreeColumnEngine();
        break;
      case 3 /* Pillars */:
        this.engine = new PillarEngine();
        break;
      case 4 /* Pager */:
        this.engine = new PagerEngine();
        break;
      case 5 /* KWin */:
        this.engine = new KwinEngine();
        break;
      default:
        console().warn("Invalid tiling engine type", type);
        this.engineType = 0 /* BTree */;
        this.engine = new BTreeEngine();
        break;
    }
    this.engine.setEngineSettings(settings);
    this.engineRootTile = this.engine.buildLayout();
  }
  getEngineSettings() {
    return this.engine.getEngineSettings();
  }
  setEngineSettings(settings) {
    this.engine.setEngineSettings(settings);
  }
  buildLayout() {
    this.engineRootTile = this.engine.buildLayout();
    return this.engineRootTile;
  }
  addWindow(window, tile, direction) {
    return this.engine.addWindow(window, tile, direction);
  }
  placeWindow(window, tile, direction) {
    return this.engine.placeWindow(window, tile, direction);
  }
  windowActivated(window) {
    return this.engine.windowActivated(window);
  }
  removeWindow(window) {
    return this.engine.removeWindow(window);
  }
  updateTiles(rootTile) {
    return this.engine.updateTiles(rootTile);
  }
};

// src/controller/config.ts
var Config = class {
  constructor(kwinApi) {
    const rc = kwinApi.readConfig;
    this.rebuildDelay = rc("RebuildDelay", 10);
    this.tileResizeAmount = rc("TileResizeAmount", 10);
    this.useDBusSaver = rc("UseDBusSaver", false);
    this.logLevel = rc("LogLevel", 1 /* Warn */);
    this.defaultEngine = rc("DefaultEngine", 0 /* BTree */);
    this.btreeSettings = {
      swapInsertSide: rc("BTreeSwapInsertSide", false),
      rotateLayout: rc("BTreeRotateLayout", false),
      insertionStyle: rc(
        "BTreeInsertionStyle",
        0 /* Shallow */
      ),
      insertInActive: rc("BTreeInsertInActive", false)
    };
    this.halfSettings = {
      swapInsertSide: rc("HalfSwapInsertSide", false),
      middleSplit: rc("HalfMiddleSplit", 0.5),
      rotateLayout: rc("HalfRotateLayout", false),
      insertInActive: rc("HalfInsertInActive", false),
      keepMaster: rc("HalfKeepMaster", false)
    };
    this.threeColumnSettings = {
      swapInsertSide: rc("ThreeColumnSwapInsertSide", false),
      side1Size: rc("ThreeColumnSide1Size", 0.25),
      side2Size: rc("ThreeColumnSide2Size", 0.25),
      rotateLayout: rc("ThreeColumnRotateLayout", false)
    };
    this.pillarSettings = {
      pillarCount: rc("PillarsPillarCount", 3),
      swapInsertSide: rc("PillarsSwapInsertSide", false),
      insertionStyle: rc(
        "PillarsInsertionStyle",
        0 /* Rows */
      ),
      rotateLayout: rc("PillarsRotateLayout", false),
      insertInActive: rc("PillarsInsertInActive", false)
    };
    this.pagerSettings = {
      pageWidth: rc("PagerPageWidth", 0.15),
      swapInsertSide: rc("PagerSwapInsertSide", false),
      rotateLayout: rc("PagerRotateLayout", false)
    };
    this.rawRegex = rc("RawRegex", false);
    let ignoreWindowClasses = rc(
      "IgnoreWindowClasses",
      "krunner, yakuake, kded, polkit, plasmashell, xwaylandvideobridge"
    );
    let ignoreWindowCaptions = rc("IgnoreWindowCaptions", "");
    let untileWindowClasses = rc("UntileWindowClasses", "");
    let untileWindowCaptions = rc("UntileWindowCaptions", "");
    if (!this.rawRegex) {
      ignoreWindowClasses = "^" + commaRegex(ignoreWindowClasses) + "$";
      ignoreWindowCaptions = "^" + commaRegex(ignoreWindowCaptions) + "$";
      untileWindowClasses = "^" + commaRegex(untileWindowClasses) + "$";
      untileWindowCaptions = "^" + commaRegex(untileWindowCaptions) + "$";
    }
    this.ignoreWindowClasses = new RegExp(ignoreWindowClasses);
    this.ignoreWindowCaptions = new RegExp(ignoreWindowCaptions);
    this.untileWindowClasses = new RegExp(untileWindowClasses);
    this.untileWindowCaptions = new RegExp(untileWindowCaptions);
    this.borders = rc("Borders", 4 /* All */);
    this.tiledWindowsBelow = rc("TiledWindowsBelow", true);
    this.tilePopups = rc("TilePopups", false);
    this.windowDragPolicy = rc("WindowDragPolicy", 1 /* Tiled */);
  }
};
function commaRegex(str) {
  return str.split(",").map((x) => x.trim()).join("|");
}

// src/controller/handlers/window.ts
var WindowHandler = class {
  constructor(window, workspace) {
    this.wasTiledBeforeMove = false;
    this.previousTile = null;
    this.window = window;
    this.workspace = workspace;
    this.wantsTiled = this.startTiled();
    this.maximized = false;
    this.window.desktopsChanged.connect(this.updateWindow.bind(this));
    this.window.activitiesChanged.connect(this.updateWindow.bind(this));
    this.window.outputChanged.connect(this.updateWindow.bind(this));
    this.window.fullScreenChanged.connect(
      this.fullscreenChanged.bind(this)
    );
    this.window.minimizedChanged.connect(this.minimizedChanged.bind(this));
    this.window.maximizedAboutToChange.connect(
      this.maximizedChanged.bind(this)
    );
    this.window.interactiveMoveResizeStarted.connect(
      this.interactiveMoveResizeStarted.bind(this)
    );
    this.window.interactiveMoveResizeStepped.connect(
      this.interactiveMoveResizeStepped.bind(this)
    );
    this.window.interactiveMoveResizeFinished.connect(
      this.interactiveMoveResizeFinished.bind(this)
    );
    this.window.tileChanged.connect(this.tileChanged.bind(this));
  }
  startTiled() {
    if (this.window.specialWindow || !config().tilePopups && (this.window.popupWindow || this.window.transient)) {
      return false;
    }
    if (!this.canBeTiled()) {
      return false;
    }
    if (config().untileWindowClasses.test(this.window.resourceClass)) {
      return false;
    }
    if (config().untileWindowCaptions.test(this.window.caption)) {
      return false;
    }
    return true;
  }
  updateWindow() {
    console().debug(
      "updating displays for window",
      this.window.resourceClass
    );
    controller().queueEvent({
      t: "updateWindow",
      window: this.window
    });
  }
  fullscreenChanged() {
    console().debug(
      "fullscreen changed on window",
      this.window.resourceClass
    );
    if (!this.canBeTiled() && controller().isWindowTiled(this.window)) {
      controller().queueEvent({
        t: "untileWindow",
        window: this.window
      });
    } else if (this.canBeTiled() && !controller().isWindowTiled(this.window) && this.wantsTiled) {
      controller().queueEvent({
        t: "tileWindow",
        window: this.window
      });
    }
    if (this.window.fullScreen) {
      controller().queuePostEvent({
        t: "setWindowProperties",
        window: this.window,
        fullscreen: false
      });
      controller().queuePostEvent({
        t: "setWindowProperties",
        window: this.window,
        fullscreen: true,
        keepAbove: true
      });
    } else {
      controller().queuePostEvent({
        t: "setWindowProperties",
        window: this.window,
        keepAbove: false
      });
    }
  }
  minimizedChanged() {
    console().debug(
      "minimized changed on window",
      this.window.resourceClass
    );
    if (!this.canBeTiled() && controller().isWindowTiled(this.window)) {
      controller().queueEvent({
        t: "untileWindow",
        window: this.window
      });
    } else if (this.canBeTiled() && !controller().isWindowTiled(this.window) && this.wantsTiled) {
      controller().queueEvent({
        t: "tileWindow",
        window: this.window
      });
    }
  }
  maximizedChanged(state) {
    console().debug(
      "maximized state changed on window",
      this.window.resourceClass
    );
    this.maximized = state !== 0 /* MaximizeRestore */;
    if (!this.canBeTiled() && controller().isWindowTiled(this.window)) {
      controller().queueEvent({
        t: "untileWindow",
        window: this.window
      });
    } else if (this.canBeTiled() && !controller().isWindowTiled(this.window) && this.wantsTiled) {
      controller().queueEvent({
        t: "tileWindow",
        window: this.window
      });
    }
  }
  // multiple step move resize -
  // if tiled and in a tile, then when move started, set is moving flag to true
  // then if it leaves the tile in a later step, untile it
  // after all that, if
  interactiveMoveResizeStarted() {
    this.wasTiledBeforeMove = controller().isWindowTiled(this.window) ?? false;
  }
  interactiveMoveResizeStepped() {
    if (!controller().isWindowTiled(this.window) || !this.canBeTiled() || this.window.tile != null) {
      return;
    }
    if (!this.wasTiledBeforeMove && config().windowDragPolicy !== 2 /* Never */) {
      return;
    }
    console().debug("move started on window", this.window.resourceClass);
    if (config().windowDragPolicy == 2 /* Never */) {
      this.wantsTiled = false;
    }
    controller().queueEvent({
      t: "untileWindow",
      window: this.window
    });
  }
  interactiveMoveResizeFinished() {
    if (!this.wantsTiled || !this.canBeTiled() || controller().isWindowTiled(this.window)) {
      return;
    }
    if (!this.wasTiledBeforeMove && config().windowDragPolicy == 1 /* Tiled */) {
      return;
    }
    console().debug("move finished on window", this.window.resourceClass);
    const cursorPos = this.workspace.cursorPos;
    controller().queueEvent({
      t: "placeWindowPoint",
      window: this.window,
      point: cursorPos
    });
  }
  // this only tracks manual insertion into a tile
  tileChanged(tile) {
    if (this.previousTile == null && tile != null) {
      this.wantsTiled = true;
      controller().queueEvent({
        t: "placeWindow",
        window: this.window,
        tile
      });
    }
    this.previousTile = tile;
  }
  canBeTiled() {
    return !(this.window.fullScreen || this.window.minimized || this.maximized);
  }
};

// src/controller/handlers/workspace.ts
var WorkspaceHandler = class {
  constructor(workspace) {
    this.workspace = workspace;
    this.previousActivated = null;
    this.currentActivated = this.workspace.activeWindow;
    this.workspace.windowAdded.connect(this.windowAdded.bind(this));
    this.workspace.windowRemoved.connect(this.windowRemoved.bind(this));
    this.workspace.windowActivated.connect(this.windowActivated.bind(this));
    this.workspace.currentActivityChanged.connect(
      this.rebuildDesktops.bind(this)
    );
    this.workspace.screensChanged.connect(this.updateDrivers.bind(this));
    this.workspace.desktopsChanged.connect(this.updateDrivers.bind(this));
    this.workspace.activityAdded.connect(this.updateDrivers.bind(this));
    this.workspace.activityRemoved.connect(this.updateDrivers.bind(this));
    this.workspace.activitiesChanged.connect(this.updateDrivers.bind(this));
  }
  windowAdded(window) {
    if (config().ignoreWindowClasses.test(window.resourceClass) || config().ignoreWindowCaptions.test(window.caption)) {
      return;
    }
    let tile, direction = void 0;
    if (this.previousActivated?.tile != null) {
      tile = this.previousActivated.tile;
      direction = directionFromPoint(
        tile.absoluteGeometry,
        this.workspace.cursorPos
      );
    }
    controller().queueEvent({
      t: "newWindow",
      window,
      tile,
      direction
    });
  }
  windowRemoved(window) {
    controller().queueEvent({
      t: "deleteWindow",
      window,
      displays: [...Display.generateWindow(window)]
    });
  }
  rebuildDesktops() {
    controller().queueEvent({ t: "rebuildDisplays" });
  }
  updateDrivers() {
    controller().queueEvent({ t: "updateDrivers" });
  }
  windowActivated(window) {
    this.previousActivated = this.currentActivated;
    this.currentActivated = window;
    const borders = config().borders;
    if (this.previousActivated !== null && (borders === 2 /* Active */ || borders === 3 /* FloatingActive */ && controller().isWindowTiled(this.previousActivated))) {
      controller().queuePostEvent({
        t: "setWindowProperties",
        window: this.previousActivated,
        noBorder: true
      });
    }
    if (window === null) {
      return;
    }
    if ((borders === 2 /* Active */ || borders === 3 /* FloatingActive */) && controller().isWindowTiled(window)) {
      controller().queuePostEvent({
        t: "setWindowProperties",
        window,
        noBorder: false
      });
    }
    controller().queueEvent({
      t: "windowActivated",
      window
    });
  }
};

// src/controller/handlers/shortcuts.ts
var ShortcutsHandler = class {
  constructor(workspace, shortcuts) {
    this.workspace = workspace;
    this.shortcuts = shortcuts;
    this.shortcuts.toggleActiveTiling().activated.connect(this.toggleActiveTiling.bind(this));
    this.shortcuts.setEngineBTree().activated.connect(
      this.setEngineType.bind(this, 0 /* BTree */)
    );
    this.shortcuts.setEngineHalf().activated.connect(
      this.setEngineType.bind(this, 1 /* Half */)
    );
    this.shortcuts.setEngineThreeColumn().activated.connect(
      this.setEngineType.bind(this, 2 /* ThreeColumn */)
    );
    this.shortcuts.setEnginePillars().activated.connect(
      this.setEngineType.bind(this, 3 /* Pillars */)
    );
    this.shortcuts.setEnginePager().activated.connect(
      this.setEngineType.bind(this, 4 /* Pager */)
    );
    this.shortcuts.setEngineKWin().activated.connect(
      this.setEngineType.bind(this, 5 /* KWin */)
    );
    this.shortcuts.activateBelow().activated.connect(
      this.activateInDirection.bind(this, 8 /* BottomEdge */)
    );
    this.shortcuts.activateAbove().activated.connect(
      this.activateInDirection.bind(this, 1 /* TopEdge */)
    );
    this.shortcuts.activateLeft().activated.connect(
      this.activateInDirection.bind(this, 2 /* LeftEdge */)
    );
    this.shortcuts.activateRight().activated.connect(
      this.activateInDirection.bind(this, 4 /* RightEdge */)
    );
    this.shortcuts.placeBelow().activated.connect(
      this.placeInDirection.bind(this, 8 /* BottomEdge */)
    );
    this.shortcuts.placeAbove().activated.connect(this.placeInDirection.bind(this, 1 /* TopEdge */));
    this.shortcuts.placeLeft().activated.connect(this.placeInDirection.bind(this, 2 /* LeftEdge */));
    this.shortcuts.placeRight().activated.connect(
      this.placeInDirection.bind(this, 4 /* RightEdge */)
    );
    this.shortcuts.resizeDown().activated.connect(
      this.resizeInDirection.bind(this, 8 /* BottomEdge */)
    );
    this.shortcuts.resizeUp().activated.connect(this.resizeInDirection.bind(this, 1 /* TopEdge */));
    this.shortcuts.resizeLeft().activated.connect(
      this.resizeInDirection.bind(this, 2 /* LeftEdge */)
    );
    this.shortcuts.resizeRight().activated.connect(
      this.resizeInDirection.bind(this, 4 /* RightEdge */)
    );
    this.shortcuts.toggleSettingsMenu().activated.connect(this.toggleSettingsMenu.bind(this));
    this.shortcuts.cycleEngine().activated.connect(this.cycleEngine.bind(this));
  }
  toggleActiveTiling() {
    const window = this.workspace.activeWindow;
    if (window == null) return;
    const windowHandler = controller().getWindowHandler(window);
    if (windowHandler == void 0) return;
    if (controller().isWindowTiled(window)) {
      windowHandler.wantsTiled = false;
      controller().queueEvent({
        t: "untileWindow",
        window
      });
    } else {
      windowHandler.wantsTiled = true;
      controller().queueEvent({
        t: "tileWindow",
        window
      });
    }
  }
  setEngineType(engineType) {
    controller().queueEvent({
      t: "changeEngine",
      display: new Display(
        this.workspace.currentDesktop,
        this.workspace.currentActivity,
        this.workspace.activeScreen
      ),
      engineType
    });
  }
  getTileInDirection(tile, rootTile, edge) {
    if (tile == rootTile) return null;
    let x = tile.absoluteGeometry.x;
    let y = tile.absoluteGeometry.y;
    switch (edge) {
      case 8 /* BottomEdge */:
        x += tile.absoluteGeometry.width / 2;
        y += tile.absoluteGeometry.height + 2;
        break;
      case 1 /* TopEdge */:
        x += tile.absoluteGeometry.width / 2;
        y -= 2;
        break;
      case 2 /* LeftEdge */:
        x -= 2;
        y += tile.absoluteGeometry.height / 2;
        break;
      case 4 /* RightEdge */:
        x += tile.absoluteGeometry.width + 2;
        y += tile.absoluteGeometry.height / 2;
        break;
      default:
        return null;
    }
    const point = qt().point(Math.floor(x), Math.floor(y));
    console().debug("selecting tile for point", point);
    return rootTile.pick(point);
  }
  activateInDirection(edge) {
    const currentTile = this.workspace.activeWindow?.tile;
    if (currentTile == null) return;
    let rootTile = currentTile;
    while (rootTile.parent != null) {
      rootTile = rootTile.parent;
    }
    const targetTile = this.getTileInDirection(currentTile, rootTile, edge);
    if (targetTile == null) return;
    console().log(
      "activateInDirection geom -",
      targetTile.absoluteGeometry
    );
    if (targetTile.windows.length == 0) return;
    this.workspace.activeWindow = targetTile.windows[0];
  }
  placeInDirection(edge) {
    const window = this.workspace.activeWindow;
    if (window === null) {
      return;
    }
    const currentTile = window.tile;
    if (currentTile === null) return;
    let rootTile = currentTile;
    while (rootTile.parent != null) {
      rootTile = rootTile.parent;
    }
    const targetTile = this.getTileInDirection(currentTile, rootTile, edge);
    if (targetTile == null) return;
    let direction = void 0;
    switch (edge) {
      case 1 /* TopEdge */:
        direction = 4 /* Vertical */;
        break;
      case 8 /* BottomEdge */:
        direction = 1 /* Down */ | 4 /* Vertical */;
        break;
      case 2 /* LeftEdge */:
        direction = 0 /* None */;
        break;
      case 4 /* RightEdge */:
        direction = 2 /* Right */;
        break;
      default:
        break;
    }
    if (edge & 8 /* BottomEdge */ || edge & 1 /* TopEdge */) {
      const currentCenter = currentTile.absoluteGeometry.x + currentTile.absoluteGeometry.width / 2;
      const targetCenter = targetTile.absoluteGeometry.x + targetTile.absoluteGeometry.width / 2;
      if (currentCenter > targetCenter && direction !== void 0) {
        direction |= 2 /* Right */;
      }
    } else if (edge & 2 /* LeftEdge */ || edge & 4 /* RightEdge */) {
      const currentCenter = currentTile.absoluteGeometry.y + currentTile.absoluteGeometry.height / 2;
      const targetCenter = targetTile.absoluteGeometry.y + targetTile.absoluteGeometry.height / 2;
      if (currentCenter > targetCenter && direction !== void 0) {
        direction |= 1 /* Down */;
      }
    }
    controller().queueEvent({
      t: "placeWindow",
      window,
      tile: targetTile,
      direction
    });
  }
  resizeInDirection(edge) {
    const currentTile = this.workspace.activeWindow?.tile;
    if (currentTile == null) return;
    let amount = config().tileResizeAmount;
    if (edge & 1 /* TopEdge */ || edge & 2 /* LeftEdge */) {
      amount *= -1;
    }
    currentTile.resizeByPixels(amount, edge);
  }
  toggleSettingsMenu() {
    controller().queuePostEvent({
      t: "toggleSettingsMenu",
      display: new Display(
        this.workspace.currentDesktop,
        this.workspace.currentActivity,
        this.workspace.activeScreen
      )
    });
  }
  cycleEngine() {
    const current = controller().getEngineType(
      new Display(
        this.workspace.currentDesktop,
        this.workspace.currentActivity,
        this.workspace.activeScreen
      )
    );
    if (current === void 0) {
      return;
    }
    const next = (current + 1) % 6 /* _Loop */;
    this.setEngineType(next);
  }
};

// src/controller/handlers/settings.ts
var SettingsHandler = class {
  constructor(settingsQml) {
    this.settingsQml = settingsQml;
    this.settingsQml.saveSettings.connect(this.saveSettings.bind(this));
    this.settingsQml.resetSettings.connect(this.resetSettings.bind(this));
  }
  show(display, engineType, engineSettings) {
    console().debug("showing settings");
    this.settingsQml.show(
      display.desktop,
      display.activity,
      display.output,
      engineType,
      engineSettings
    );
  }
  hide() {
    this.settingsQml.hide();
  }
  isVisible() {
    return this.settingsQml.visible;
  }
  saveSettings(desktop, activity, output, engineType, engineSettings) {
    controller().queueEvent({
      t: "changeEngine",
      display: new Display(desktop, activity, output),
      engineType,
      engineSettings
    });
  }
  resetSettings(desktop, activity, output) {
    controller().queueEvent({
      t: "resetEngine",
      display: new Display(desktop, activity, output)
    });
  }
};

// src/controller/handlers/dbus.ts
function settingsBundle(engineType, engineSettings) {
  const bundle = {
    engineType,
    engineSettings
  };
  return JSON.stringify(bundle);
}
var DBusHandler = class {
  constructor(dbusQml) {
    this.dbusQml = dbusQml;
    dbusQml.getSettings().finished.connect(this.getSettingsCallback.bind(this));
  }
  getSettings(display) {
    console().debug("getSettings called");
    this.dbusQml.getSettings().arguments = [display.toString()];
    this.dbusQml.getSettings().call();
  }
  getSettingsCallback([
    desktopIdStr,
    settingsBundleStr
  ]) {
    console().debug(
      "getSettings dbus callback activated -",
      desktopIdStr,
      settingsBundleStr
    );
    try {
      const display = controller().parseDisplay(desktopIdStr);
      if (display === void 0) return;
      const settingsBundle2 = JSON.parse(
        settingsBundleStr
      );
      controller().queueEvent(
        {
          t: "changeEngine",
          display,
          engineType: settingsBundle2.engineType,
          engineSettings: settingsBundle2.engineSettings,
          noDBusUpdate: true
        },
        true
      );
    } catch (e) {
      console().error(e);
    }
  }
  setSettings(display, engineType, engineSettings) {
    console().debug("setSettings called");
    this.dbusQml.setSettings().arguments = [
      display.toString(),
      settingsBundle(engineType, engineSettings)
    ];
    this.dbusQml.setSettings().call();
  }
  resetSettings(display) {
    console().debug("resetSettings called");
    this.dbusQml.resetSettings().arguments = [display.toString()];
    this.dbusQml.resetSettings().call();
  }
};

// src/controller/console.ts
var Console = class {
  constructor(console2) {
    this.console = console2;
  }
  debug(...args) {
    if (config().logLevel < 3 /* Debug */) return;
    this.console.info("Polonium DBG:", ...args);
  }
  log(...args) {
    if (config().logLevel < 2 /* Log */) return;
    this.console.info("Polonium LOG:", ...args);
  }
  warn(...args) {
    if (config().logLevel < 1 /* Warn */) return;
    this.console.warn("Polonium WRN:", ...args);
  }
  error(...args) {
    this.console.error("Polonium ERR:", ...args);
  }
};

// src/driver/buildlayout.ts
function buildLayout(kwinRootTile, engineRootTile) {
  const tileMap = /* @__PURE__ */ new Map();
  const queue = new Queue();
  queue.push([kwinRootTile, engineRootTile]);
  while (!queue.isEmpty) {
    const [kwinTile, engineTile] = queue.pop();
    if (kwinTile == null) {
      console().warn("kwin tile is null");
      continue;
    }
    tileMap.set(kwinTile, engineTile);
    if (kwinTile.layoutDirection !== engineTile.layoutDirection) {
      while (kwinTile.tiles.length > 0) {
        kwinTile.tiles[kwinTile.tiles.length - 1].remove();
      }
      kwinTile.layoutDirection = engineTile.layoutDirection;
    }
    console().debug("kwin children", kwinTile.tiles.length);
    console().debug("engine children", engineTile.children.length);
    if (engineTile.children.length == 1) {
      console().warn(
        "engine tile at",
        kwinTile.absoluteGeometry,
        "has only one child"
      );
      while (kwinTile.tiles.length > 0) {
        kwinTile.tiles[kwinTile.tiles.length - 1].remove();
      }
      queue.push([kwinTile, engineTile.children[0]]);
    } else {
      matchChildren(kwinTile, engineTile);
    }
    if (engineTile.children.length > 1) {
      for (let i = 0; i < engineTile.children.length; i += 1) {
        queue.push([kwinTile.tiles[i], engineTile.children[i]]);
      }
    }
  }
  return tileMap;
}
function matchChildren(kwinTile, engineTile) {
  const layoutDirection = engineTile.layoutDirection;
  while (kwinTile.tiles.length > engineTile.children.length) {
    kwinTile.tiles[kwinTile.tiles.length - 1].remove();
  }
  if (engineTile.children.length === 0) return;
  for (let i = 0; i < kwinTile.tiles.length - 1; i += 1) {
    setChildMinSize(kwinTile, i);
  }
  while (kwinTile.tiles.length < engineTile.children.length) {
    if (kwinTile.tiles.length == 0) {
      kwinTile.split(layoutDirection);
      setChildMinSize(kwinTile, 0);
    } else {
      kwinTile.tiles[kwinTile.tiles.length - 1].split(layoutDirection);
      setChildMinSize(kwinTile, kwinTile.tiles.length - 2);
    }
  }
  for (let i = kwinTile.tiles.length - 1; i >= 0; i -= 1) {
    setChildRelativeSize(kwinTile, engineTile, i);
  }
}
function setChildMinSize(kwinTile, index) {
  const minSize = 0.15001;
  console().debug("setMinChildSize on idx", index);
  const kwinChild = kwinTile.tiles[index];
  const parentGeom = kwinTile.relativeGeometry;
  console().debug("previous dimensions", kwinChild.relativeGeometry);
  const geom = qt().rect(
    parentGeom.x,
    parentGeom.y,
    parentGeom.width,
    parentGeom.height
  );
  if (kwinTile.layoutDirection === 1 /* Horizontal */) {
    geom.width *= minSize;
    geom.x += geom.width * index;
  } else if (kwinTile.layoutDirection === 2 /* Vertical */) {
    geom.height *= minSize;
    geom.y += geom.height * index;
  }
  console().debug("target dimensions", geom);
  kwinChild.relativeGeometry = geom;
  console().debug("new dimensions", kwinChild.relativeGeometry);
}
function setChildRelativeSize(kwinTile, engineTile, index) {
  console().debug("setChildRelativeSize on idx", index);
  const totalSize = engineTile.totalChildrenSize();
  const kwinChild = kwinTile.tiles[index];
  const engineChild = engineTile.children[index];
  console().debug("target size -", engineChild.size);
  const oldGeom = kwinChild.relativeGeometry;
  console().debug("previous dimensions -", oldGeom);
  const geom = qt().rect(
    kwinTile.relativeGeometry.x,
    kwinTile.relativeGeometry.y,
    kwinTile.relativeGeometry.width,
    kwinTile.relativeGeometry.height
  );
  if (engineTile.layoutDirection === 1 /* Horizontal */) {
    geom.width *= engineChild.size / totalSize;
    let previousChildrenSize = 0;
    for (let i = 0; i < index; i += 1) {
      previousChildrenSize += engineTile.children[i].size;
    }
    previousChildrenSize /= totalSize;
    previousChildrenSize *= kwinTile.relativeGeometry.width;
    geom.x += previousChildrenSize;
  } else if (engineTile.layoutDirection === 2 /* Vertical */) {
    geom.height *= engineChild.size / totalSize;
    let previousChildrenSize = 0;
    for (let i = 0; i < index; i += 1) {
      previousChildrenSize += engineTile.children[i].size;
    }
    previousChildrenSize /= totalSize;
    previousChildrenSize *= kwinTile.relativeGeometry.height;
    geom.y += previousChildrenSize;
  }
  console().debug("target dimensions -", geom);
  kwinChild.relativeGeometry = geom;
  console().debug("final dimensions -", kwinChild.relativeGeometry);
}

// src/driver/updatetiles.ts
function updateTiles(rootTile, tileMap) {
  let kwinRootTile = null;
  for (const [kwinTile, engineTile] of tileMap) {
    if (engineTile !== rootTile) {
      continue;
    }
    kwinRootTile = kwinTile;
    break;
  }
  if (kwinRootTile == null) {
    return rootTile;
  }
  const queue = new Queue();
  queue.push([kwinRootTile, rootTile]);
  while (!queue.isEmpty) {
    const [kwinTile, engineTile] = queue.pop();
    engineTile.layoutDirection = kwinTile.layoutDirection;
    let relativeSize = 1;
    if (kwinTile.parent != null) {
      const parent = kwinTile.parent;
      const direction = parent.layoutDirection;
      if (direction === 1 /* Horizontal */) {
        relativeSize = kwinTile.relativeGeometry.width / parent.relativeGeometry.width;
      } else if (direction === 2 /* Vertical */) {
        relativeSize = kwinTile.relativeGeometry.height / parent.relativeGeometry.height;
      } else {
        relativeSize /= parent.tiles.length;
      }
      relativeSize *= parent.tiles.length;
    }
    engineTile.size = relativeSize;
    for (let i = 0; i < kwinTile.tiles.length; i += 1) {
      updateChildTile(kwinTile, engineTile, tileMap, i);
      queue.push([kwinTile.tiles[i], engineTile.children[i]]);
    }
  }
  return rootTile;
}
function updateChildTile(kwinTile, engineTile, tileMap, idx) {
  const kwinChild = kwinTile.tiles[idx];
  let engineChild = tileMap.get(kwinChild);
  if (engineChild === void 0) {
    engineChild = new Tile(engineTile);
    engineTile.children.splice(idx, 0, engineChild);
    tileMap.set(kwinChild, engineChild);
  }
}

// src/driver/index.ts
var Driver = class {
  constructor(engineType, engineSettings) {
    this.engineRootTile = null;
    this.tileMap = /* @__PURE__ */ new Map();
    this.hookedTiles = /* @__PURE__ */ new Set();
    this.windowMap = /* @__PURE__ */ new Map();
    this.untiledWindows = /* @__PURE__ */ new Set();
    this.savedActiveWindow = null;
    if (engineSettings === void 0) {
      engineSettings = getConfigEngineSettings(engineType);
    }
    this.tilingEngine = new TilingEngine(engineType, engineSettings);
  }
  setEngineType(engineType, engineSettings) {
    this.tilingEngine = new TilingEngine(engineType, engineSettings);
    for (const engineWindow of this.windowMap.values()) {
      this.tilingEngine.addWindow(engineWindow);
    }
  }
  changeTilingEngine(engineType, engineSettings) {
    if (engineType !== void 0 && this.tilingEngine.engineType != engineType) {
      if (engineSettings === void 0) {
        engineSettings = getConfigEngineSettings(engineType);
      }
      this.setEngineType(engineType, engineSettings);
    } else if (engineSettings !== void 0) {
      this.tilingEngine.setEngineSettings(engineSettings);
    }
  }
  hasWindow(kwinWindow) {
    return this.windowMap.has(kwinWindow);
  }
  hasTile(kwinTile) {
    return this.tileMap.has(kwinTile);
  }
  getEngineType() {
    return this.tilingEngine.engineType;
  }
  getEngineSettings() {
    return this.tilingEngine.getEngineSettings();
  }
  isWindowTiled(kwinWindow) {
    if (!this.windowMap.has(kwinWindow)) {
      return void 0;
    }
    return !this.untiledWindows.has(kwinWindow);
  }
  resetTilingEngine() {
    const defaultEngine = config().defaultEngine;
    const defaultSettings = getConfigEngineSettings(defaultEngine);
    if (this.tilingEngine.engineType !== defaultEngine) {
      this.setEngineType(defaultEngine, defaultSettings);
    } else {
      this.tilingEngine.setEngineSettings(defaultSettings);
    }
  }
  buildLayout(rootTile, display) {
    for (const [kwinWindow, _ew] of this.windowMap) {
      if (!controller().windowExists(kwinWindow) || !(kwinWindow.desktops.includes(display.desktop) || kwinWindow.onAllDesktops) || !kwinWindow.activities.includes(display.activity) || kwinWindow.output !== display.output) {
        console().warn("invalid window in windowMap");
        this.removeWindow(kwinWindow);
      }
    }
    this.engineRootTile = this.tilingEngine.buildLayout();
    this.tileMap = buildLayout(rootTile, this.engineRootTile);
    for (const hookedTile of this.hookedTiles) {
      if (!this.tileMap.has(hookedTile)) {
        this.hookedTiles.delete(hookedTile);
      }
    }
    const invertedWindowMap = new Map(
      Array.from(this.windowMap, (a) => [a[1], a[0]])
    );
    const tiledWindows = /* @__PURE__ */ new Set();
    for (const [kwinTile, engineTile] of this.tileMap) {
      if (!this.hookedTiles.has(kwinTile)) {
        kwinTile.relativeGeometryChanged.connect(
          this.updateTileSizesCallback.bind(this, display)
        );
        kwinTile.childTilesChanged.connect(
          this.updateTileCountCallback.bind(this, display)
        );
        this.hookedTiles.add(kwinTile);
      }
      for (const engineWindow of engineTile.windows) {
        const kwinWindow = invertedWindowMap.get(engineWindow);
        if (kwinWindow === void 0) {
          continue;
        }
        console().debug(
          "setting",
          kwinWindow.resourceClass,
          "as tiled"
        );
        if (this.untiledWindows.has(kwinWindow)) {
          this.untiledWindows.delete(kwinWindow);
        }
        setTiledProps(kwinWindow);
        if (kwinWindow.tile !== kwinTile) kwinTile.manage(kwinWindow);
        tiledWindows.add(kwinWindow);
      }
    }
    for (const kwinWindow of this.windowMap.keys()) {
      if (!tiledWindows.has(kwinWindow)) {
        console().debug(
          "setting",
          kwinWindow.resourceClass,
          "as untiled"
        );
        this.untiledWindows.add(kwinWindow);
        if (kwinWindow.tile != null && this.tileMap.has(kwinWindow.tile)) {
          kwinWindow.tile.unmanage(kwinWindow);
          setUntiledProps(kwinWindow);
        } else if (kwinWindow.tile == null) {
          setUntiledProps(kwinWindow);
        }
      }
    }
  }
  initializeWindow(kwinWindow) {
    if (this.windowMap.has(kwinWindow)) {
      return this.windowMap.get(kwinWindow);
    }
    const engineWindow = new Window(
      kwinWindow.internalId,
      kwinWindow.caption,
      kwinWindow.minSize
    );
    this.windowMap.set(kwinWindow, engineWindow);
    return engineWindow;
  }
  addWindow(kwinWindow, tile, direction) {
    if (this.windowMap.has(kwinWindow)) {
      console().warn(
        "initializeWindow error - window already exists in map"
      );
      return;
    }
    const window = this.initializeWindow(kwinWindow);
    this.tilingEngine.addWindow(
      window,
      tile ? this.tileMap.get(tile) : void 0,
      direction
    );
    if (this.savedActiveWindow === kwinWindow) {
      this.tilingEngine.windowActivated(window);
    }
  }
  addWindowUntiled(kwinWindow) {
    if (this.windowMap.has(kwinWindow)) {
      console().warn(
        "initializeWindow error - window already exists in map"
      );
      return;
    }
    this.initializeWindow(kwinWindow);
  }
  tileWindow(kwinWindow) {
    const window = this.windowMap.get(kwinWindow);
    if (window === void 0) {
      console().warn("tileWindow error - window not found in map");
      return;
    }
    this.tilingEngine.addWindow(window);
    if (this.savedActiveWindow === kwinWindow) {
      this.tilingEngine.windowActivated(window);
    }
  }
  untileWindow(kwinWindow) {
    const window = this.windowMap.get(kwinWindow);
    if (window === void 0) {
      console().warn("untileWindow error - window not found in map");
      return;
    }
    this.tilingEngine.removeWindow(window);
  }
  placeWindow(kwinWindow, kwinTile, direction) {
    let window = this.initializeWindow(kwinWindow);
    const tile = this.tileMap.get(kwinTile);
    if (tile == void 0) {
      console().warn("tile undefined during window placement");
      this.tilingEngine.addWindow(window);
      return;
    }
    this.tilingEngine.placeWindow(window, tile, direction);
    if (this.savedActiveWindow === kwinWindow) {
      this.tilingEngine.windowActivated(window);
    }
  }
  windowActivated(kwinWindow) {
    this.savedActiveWindow = kwinWindow;
    const engineWindow = this.windowMap.get(kwinWindow);
    if (engineWindow === void 0) {
      return false;
    }
    return this.tilingEngine.windowActivated(engineWindow);
  }
  removeWindow(kwinWindow) {
    if (this.untiledWindows.has(kwinWindow)) {
      this.untiledWindows.delete(kwinWindow);
    } else if (controller().windowExists(kwinWindow)) {
      setUntiledProps(kwinWindow);
      if (kwinWindow.tile != null && this.tileMap.has(kwinWindow.tile)) {
        kwinWindow.tile.unmanage(kwinWindow);
      }
    }
    const engineWindow = this.windowMap.get(kwinWindow);
    if (engineWindow === void 0) {
      console().warn(
        "Window",
        kwinWindow?.resourceClass,
        "not registered in windowMap"
      );
      return;
    }
    this.tilingEngine.removeWindow(engineWindow);
    this.windowMap.delete(kwinWindow);
  }
  // as of right now, can only update sizes (ie cannot add/remove tiles)
  updateTiles() {
    if (this.engineRootTile === null) {
      console().warn("updateTiles called, but engine layout not built");
      return;
    }
    const tile = updateTiles(this.engineRootTile, this.tileMap);
    this.tilingEngine.updateTiles(tile);
  }
  updateTileSizesCallback(display) {
    controller().queueEvent({
      t: "updateTiles",
      display,
      rebuild: false
    });
  }
  // when updating tile count we want to rebuild as for most engines this is an error
  // for kwin this is fine though
  updateTileCountCallback(display) {
    controller().queueEvent({
      t: "updateTiles",
      display,
      rebuild: true
    });
  }
};
function getConfigEngineSettings(engineType) {
  switch (engineType) {
    case 0 /* BTree */:
      return config().btreeSettings;
    case 1 /* Half */:
      return config().halfSettings;
    case 2 /* ThreeColumn */:
      return config().threeColumnSettings;
    case 3 /* Pillars */:
      return config().pillarSettings;
    case 4 /* Pager */:
      return config().pagerSettings;
    case 5 /* KWin */:
      return {};
    default:
      console().error("engine type", engineType, "is invalid");
      return {};
  }
}
function setTiledProps(window) {
  if (config().tiledWindowsBelow) {
    window.keepBelow = true;
  }
  if (config().borders === 1 /* Floating */ || config().borders === 0 /* None */ || (config().borders === 2 /* Active */ || config().borders === 3 /* FloatingActive */) && !window.active) {
    window.noBorder = true;
  }
  window.setMaximize(false, false);
}
function setUntiledProps(window) {
  if (config().tiledWindowsBelow) {
    window.keepBelow = false;
  }
  if (config().borders === 1 /* Floating */ || config().borders === 3 /* FloatingActive */) {
    window.noBorder = false;
  }
}

// src/controller/index.ts
var Controller = class {
  constructor(qmlApi, qmlObjects) {
    this.eventQueue = new Queue();
    this.postEventQueue = new Queue();
    this.processingEvents = false;
    this.drivers = /* @__PURE__ */ new Map();
    this.windowHandlers = /* @__PURE__ */ new Map();
    this.previousDisplays = /* @__PURE__ */ new Map();
    this.dbusHandler = null;
    this.workspace = qmlApi.workspace;
    this.qmlObjects = qmlObjects;
    this.eventTimer = this.qmlObjects.eventTimer;
    this.eventTimer.interval = config().rebuildDelay;
    this.eventTimer.repeat = false;
    this.eventTimer.triggered.connect(this.processEvents.bind(this));
    if (config().useDBusSaver) {
      this.dbusHandler = new DBusHandler(this.qmlObjects.dbus);
    }
    this.settingsHandler = new SettingsHandler(this.qmlObjects.settings);
    this.workspaceHandler = new WorkspaceHandler(this.workspace);
    this.shortcutsHandler = new ShortcutsHandler(
      this.workspace,
      this.qmlObjects.shortcuts
    );
    this.updateDrivers();
  }
  queueEvent(ev, forcePush = false) {
    if (this.processingEvents && !forcePush) return;
    this.eventQueue.push(ev);
    this.eventTimer.start();
  }
  queuePostEvent(ev, forcePush = false) {
    if (this.processingEvents && !forcePush) return;
    this.postEventQueue.push(ev);
    this.eventTimer.start();
  }
  processEvents() {
    this.processingEvents = true;
    const queue = simplifyEvents(this.eventQueue);
    this.eventQueue = new Queue();
    console().debug("Handling", queue.size, "event(s)");
    const rebuildDisplays = /* @__PURE__ */ new Map();
    while (!queue.isEmpty) {
      const ev = queue.pop();
      if (ev === void 0) {
        break;
      }
      const displays = this.handleEvent(ev);
      for (const display of displays) {
        rebuildDisplays.set(display.toSymbol(), display);
      }
    }
    for (const [_, display] of rebuildDisplays) {
      if (display.desktop == void 0 || display.output == void 0) {
        continue;
      }
      if (display.activity !== this.workspace.currentActivity) {
        continue;
      }
      console().debug("Rebuilding for display", display.toString());
      const driver = this.getDriver(display);
      const rootTile = this.workspace.rootTile(
        display.output,
        display.desktop
      );
      if (driver != void 0 && rootTile != void 0) {
        driver.buildLayout(rootTile, display);
      } else {
        console().error(
          "no driver found for display",
          display.toString()
        );
        continue;
      }
    }
    const postQueue = simplifyPostEvents(this.postEventQueue);
    this.postEventQueue = new Queue();
    console().debug("Handling", postQueue.size, "post event(s)");
    while (!postQueue.isEmpty) {
      const ev = postQueue.pop();
      if (ev === void 0) {
        break;
      }
      this.handlePostEvent(ev);
    }
    this.processingEvents = false;
  }
  // returns a list of displays that need a rebuild
  // one event returning yes guarantees a rebuild
  // error handling - break in case statement to exit and log error message
  handleEvent(ev) {
    console().debug("handling event", ev.t);
    try {
      switch (ev.t) {
        case "newWindow":
          return this.evNewWindow(
            ev.window,
            ev.forceTile,
            ev.tile,
            ev.direction
          );
        case "deleteWindow":
          return this.evDeleteWindow(ev.window, ev.displays);
        case "updateWindow":
          return this.evUpdateWindow(ev.window);
        case "tileWindow":
          return this.evTileWindow(ev.window);
        case "untileWindow":
          return this.evUntileWindow(ev.window);
        case "placeWindow":
          return this.evPlaceWindow(ev.window, ev.tile, ev.direction);
        case "placeWindowPoint":
          return this.evPlaceWindowPoint(ev.window, ev.point);
        case "windowActivated":
          return this.evWindowActivated(ev.window);
        case "updateDrivers":
          return this.updateDrivers();
        case "rebuildDisplays":
          return this.displaysToRebuild();
        case "updateTiles":
          return this.evUpdateTiles(ev.display, ev.rebuild);
        case "changeEngine":
          return this.evChangeEngine(
            ev.display,
            ev.engineType,
            ev.engineSettings,
            ev.noDBusUpdate
          );
        case "resetEngine":
          return this.evResetEngine(ev.display);
        default: {
          console().error("invalid event type", ev.t);
          return [];
        }
      }
    } catch (e) {
      console().error("event type", ev.t, "failed to execute");
      console().error("error message -", e.message);
    }
    return [];
  }
  evNewWindow(window, forceTile, tile, direction) {
    console().log("registering window", window.resourceClass);
    const handler = new WindowHandler(window, this.workspace);
    this.windowHandlers.set(window, handler);
    this.previousDisplays.set(window, [...Display.generateWindow(window)]);
    const ret = [];
    for (const display of Display.generateWindow(window)) {
      const driver = this.getDriver(display);
      if (driver === void 0) {
        continue;
      }
      if (forceTile === false || forceTile === void 0 && !handler.wantsTiled) {
        driver.addWindowUntiled(window);
      } else if (forceTile === true && tile != void 0 && driver.hasTile(tile)) {
        driver.placeWindow(window, tile, direction);
      } else {
        driver.addWindow(window, tile, direction);
      }
      ret.push(display);
    }
    return ret;
  }
  evDeleteWindow(window, displays) {
    console().log("destroying window", window.resourceClass);
    if (this.previousDisplays.has(window)) {
      this.previousDisplays.delete(window);
    }
    const ret = [];
    for (const display of displays) {
      this.getDriver(display)?.removeWindow(window);
      ret.push(display);
    }
    this.windowHandlers.delete(window);
    return ret;
  }
  evUpdateWindow(window) {
    console().log("updating window", window.resourceClass);
    const newDisplays = [...Display.generateWindow(window)];
    const oldDisplays = this.previousDisplays.get(window);
    if (oldDisplays === void 0) {
      return [];
    }
    let tiled = false;
    const ret = [];
    for (const oldDisplay of oldDisplays) {
      const driver = this.getDriver(oldDisplay);
      if (driver === void 0) {
        continue;
      }
      if (driver.isWindowTiled(window)) {
        tiled = true;
      }
      if (newDisplays.some((d) => d.equals(oldDisplay))) {
        continue;
      }
      driver.removeWindow(window);
      ret.push(oldDisplay);
    }
    for (const newDisplay of newDisplays) {
      if (oldDisplays.some((d) => d.equals(newDisplay))) {
        continue;
      }
      const driver = this.getDriver(newDisplay);
      if (driver === void 0) {
        continue;
      }
      if (tiled) {
        driver.addWindow(window);
      } else {
        driver.addWindowUntiled(window);
      }
      ret.push(newDisplay);
    }
    this.previousDisplays.set(window, newDisplays);
    return ret;
  }
  evTileWindow(window) {
    console().log("tiling window", window.resourceClass);
    const ret = [];
    for (const display of Display.generateWindow(window)) {
      const driver = this.getDriver(display);
      if (driver === void 0) {
        throw new Error(
          "driver not found for display " + display.toString()
        );
      }
      ret.push(display);
      driver.tileWindow(window);
    }
    return ret;
  }
  evUntileWindow(window) {
    console().log("untiling window", window.resourceClass);
    const ret = [];
    for (const display of Display.generateWindow(window)) {
      const driver = this.getDriver(display);
      if (driver === void 0) {
        throw new Error(
          "driver not found for display " + display.toString()
        );
      }
      ret.push(display);
      driver.untileWindow(window);
    }
    return ret;
  }
  evPlaceWindow(window, tile, direction) {
    console().log(
      "placing window",
      window.resourceClass,
      "in tile at",
      tile.absoluteGeometry
    );
    const displays = [];
    for (const display of Display.generateWindow(window)) {
      const driver = this.getDriver(display);
      if (driver == void 0) continue;
      if (!driver.hasTile(tile)) {
        if (driver.hasWindow(window)) {
          driver.tileWindow(window);
        } else {
          driver.addWindow(window);
        }
        continue;
      }
      driver.placeWindow(window, tile, direction);
      displays.push(display);
    }
    return displays;
  }
  evPlaceWindowPoint(window, point) {
    console().log(
      "placing window",
      window.resourceClass,
      "at point",
      point
    );
    const displays = [];
    for (const display of Display.generateWindow(window)) {
      const driver = this.getDriver(display);
      if (driver == void 0) continue;
      displays.push(display);
      if (display.activity !== this.workspace.currentActivity) {
        if (driver.hasWindow(window)) {
          driver.tileWindow(window);
        } else {
          driver.addWindow(window);
        }
        continue;
      }
      const rootTile = this.workspace.rootTile(
        display.output,
        display.desktop
      );
      const tile = rootTile.tiles.length == 0 ? rootTile : rootTile.pick(point);
      if (tile === null || !driver.hasTile(tile)) {
        if (driver.hasWindow(window)) {
          driver.tileWindow(window);
        } else {
          driver.addWindow(window);
        }
      } else {
        const direction = directionFromPoint(
          tile.absoluteGeometry,
          point
        );
        driver.placeWindow(window, tile, direction);
      }
    }
    return displays;
  }
  evWindowActivated(window) {
    console().log("window activated", window.resourceClass);
    const displays = [];
    for (const display of Display.generateWindow(window)) {
      const driver = this.getDriver(display);
      if (driver == void 0) continue;
      if (driver.windowActivated(window)) {
        displays.push(display);
      }
    }
    return displays;
  }
  updateDrivers() {
    const ret = [];
    for (const display of Display.generate(
      this.workspace.desktops,
      this.workspace.activities,
      this.workspace.screens
    )) {
      const id = display.toSymbol();
      const driver = this.drivers.get(id);
      if (driver === void 0) {
        console().debug(
          "adding driver for display",
          display.toString()
        );
        const driver2 = new Driver(config().defaultEngine);
        this.drivers.set(id, driver2);
        this.dbusHandler?.getSettings(display);
        ret.push(display);
      }
    }
    return ret;
  }
  displaysToRebuild() {
    const displays = [];
    for (const display of Display.generate(
      this.workspace.desktops,
      [this.workspace.currentActivity],
      this.workspace.screens
    )) {
      if (this.getDriver(display) !== void 0) {
        displays.push(display);
      }
    }
    return displays;
  }
  evUpdateTiles(display, rebuild) {
    console().log("updating tiles for display", display.toString());
    const driver = this.getDriver(display);
    if (driver === void 0) {
      return [];
    }
    const oldSettings = JSON.stringify(driver.getEngineSettings());
    driver.updateTiles();
    const settings = driver.getEngineSettings();
    if (oldSettings !== JSON.stringify(settings)) {
      this.dbusHandler?.setSettings(
        display,
        driver.getEngineType(),
        settings
      );
    }
    return rebuild ? [display] : [];
  }
  evChangeEngine(display, engineType, engineSettings, noDBusUpdate) {
    console().log(
      "changing engine type/settings for display",
      display.toString()
    );
    const driver = this.getDriver(display);
    if (driver === void 0) {
      throw new Error("no driver for display " + display.toString());
    }
    const oldEngine = driver.getEngineType();
    const oldSettings = JSON.stringify(driver.getEngineSettings());
    driver.changeTilingEngine(engineType, engineSettings);
    const engine = driver.getEngineType();
    const settings = driver.getEngineSettings();
    if (oldEngine === engine && oldSettings === JSON.stringify(settings)) {
      return [];
    }
    if (this.settingsHandler.isVisible()) {
      this.settingsHandler.show(display, engine, settings);
    }
    if (noDBusUpdate === void 0 || !noDBusUpdate) {
      this.dbusHandler?.setSettings(display, engine, settings);
    }
    return [display];
  }
  evResetEngine(display) {
    console().log(
      "resetting to default engine settings for display",
      display.toString()
    );
    const driver = this.getDriver(display);
    if (driver === void 0) {
      throw new Error(
        "driver undefined for display " + display.toString()
      );
    }
    const oldEngine = driver.getEngineType();
    const oldSettings = JSON.stringify(driver.getEngineSettings());
    driver.resetTilingEngine();
    this.dbusHandler?.resetSettings(display);
    const engine = driver.getEngineType();
    const settings = driver.getEngineSettings();
    if (oldEngine === engine && oldSettings === JSON.stringify(settings)) {
      return [];
    }
    if (this.settingsHandler.isVisible()) {
      this.settingsHandler.show(display, engine, settings);
    }
    return [display];
  }
  handlePostEvent(ev) {
    console().debug("handling post event", ev.t);
    switch (ev.t) {
      case "setWindowProperties": {
        if (!this.windowExists(ev.window)) {
          break;
        }
        console().log(
          "setting properties for window",
          ev.window.resourceClass
        );
        if (ev.fullscreen !== void 0) {
          ev.window.fullScreen = ev.fullscreen;
        }
        if (ev.noBorder !== void 0) {
          ev.window.noBorder = ev.noBorder;
        }
        if (ev.keepAbove !== void 0) {
          ev.window.keepAbove = ev.keepAbove;
        }
        return;
      }
      case "toggleSettingsMenu": {
        console().log("toggling settings menu");
        if (this.settingsHandler.isVisible()) {
          this.settingsHandler.hide();
          return;
        }
        const driver = this.getDriver(ev.display);
        if (driver === void 0) {
          break;
        }
        this.settingsHandler.show(
          ev.display,
          driver.getEngineType(),
          driver.getEngineSettings()
        );
        return;
      }
      default: {
        console().error("invalid post event type", ev.t);
        return;
      }
    }
    console().error("post event type", ev.t, "failed to execute");
    return;
  }
  parseDisplay(display) {
    let str;
    if (typeof display === "symbol") {
      str = Symbol.keyFor(display);
    } else if (typeof display === "string") {
      str = display;
    }
    if (str === void 0) {
      return void 0;
    }
    let parsed;
    try {
      parsed = JSON.parse(str);
    } catch (_) {
      return void 0;
    }
    const d = this.workspace.desktops.find((d2) => d2.id === parsed.d);
    const a = this.workspace.activities.find((a2) => a2 === parsed.a);
    const o = this.workspace.screens.find((s) => s.name === parsed.o);
    if (d === void 0 || a === void 0 || o === void 0) {
      return void 0;
    }
    return new Display(d, a, o);
  }
  // gets a driver, if it doesn't exist then it calls updateDrivers and tries to get it again.
  // if it still doesn't exist, then it returns undefined.
  getDriver(display) {
    let id;
    if (typeof display === "string") {
      id = Symbol.for(display);
    } else if (typeof display === "symbol") {
      id = display;
    } else if (typeof display === "object") {
      id = display.toSymbol();
    } else {
      console().error("Invalid call to getDriver");
      return void 0;
    }
    let driver = this.drivers.get(id);
    if (driver !== void 0) return driver;
    console().warn(
      "driver not found for id",
      id,
      "updating drivers and trying again"
    );
    this.updateDrivers();
    driver = this.drivers.get(id);
    if (driver === void 0) {
      console().error("driver was still not found for id", id);
    }
    return driver;
  }
  getWindowHandler(window) {
    return this.windowHandlers.get(window);
  }
  // sometimes the window can be destroyed before rebuild but the ref will still exist, so make sure it exists before calling stuff on it
  windowExists(window) {
    return window !== null && window !== void 0 && this.workspace.windows.includes(window);
  }
  // avoid making driver instance public and get current tiling layout to enable cycling
  getEngineType(display) {
    return this.drivers.get(display.toSymbol())?.getEngineType();
  }
  isWindowTiled(window, display) {
    if (display != void 0) {
      return this.getDriver(display)?.isWindowTiled(window);
    }
    for (const display2 of Display.generateWindow(window)) {
      const driver = this.getDriver(display2);
      if (driver?.isWindowTiled(window)) {
        return true;
      }
    }
    return false;
  }
};
var controllerObj;
var consoleObj;
var configObj;
var qtObject;
function initializeController(qmlApi, qmlObjects) {
  configObj = new Config(qmlApi.kwin);
  consoleObj = new Console(qmlApi.console);
  qtObject = qmlApi.qt;
  console().debug("config -", JSON.stringify(config()));
  controllerObj = new Controller(qmlApi, qmlObjects);
  console().log("controller initialized. Welcome to Polonium!");
}
function controller() {
  return controllerObj;
}
function console() {
  return consoleObj;
}
function config() {
  return configObj;
}
function qt() {
  return qtObject;
}

// src/index.ts
function main(api, qmlObjects) {
  Display.setWorkspace(api.workspace);
  const ctrl = initializeController(api, qmlObjects);
}
export {
  main
};
