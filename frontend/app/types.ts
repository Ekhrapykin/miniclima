export interface Sernum {
  serial?: string;
  firmware?: string;
  sp?: number;
  lo?: number;
  hi?: number;
  hy?: number;
  lt?: number;
  rhc?: number;
}

export interface Vals {
  state?: string;
  rh?: number;
  t?: number;
  t1?: number;
  t2?: number;
  flag?: string;
}
