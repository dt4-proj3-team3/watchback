import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Header({ values }) {
  return (
    <>
    <div style={toReactStyle("position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;height:64px;padding:0 32px;background:#FFFFFF;border-bottom:1px solid #E4E6E1;")}>
      <div style={toReactStyle("display:flex;align-items:center;gap:26px")}>
        <div style={toReactStyle("display:flex;align-items:center;gap:10px;cursor:pointer")} onClick={values.goToDashboard}>
          <div style={toReactStyle("width:26px;height:26px;border-radius:7px;background:#2F8F5B;display:flex;align-items:center;justify-content:center")}>
            <div style={toReactStyle("width:9px;height:9px;border-radius:2px;background:#FFFFFF;transform:rotate(45deg)")}></div>
          </div>
          <span style={toReactStyle("font-size:16px;font-weight:700;letter-spacing:-0.01em")}>
            {"Watchback"}
          </span>
        </div>
        <div style={toReactStyle("display:flex;align-items:center;gap:4px")}>
          {values.navTabs.map((tab, _index0) => (
            <Fragment key={_index0}>
              <div style={toReactStyle(`${tab.style}`)} onClick={tab.onClick}>
                {`${tab.label}`}
              </div>
            </Fragment>
          ))}
        </div>
      </div>
      <div style={toReactStyle("display:flex;align-items:center;gap:16px")}>
        <span style={toReactStyle("font-size:13px;color:#5B6058")}>
          {"novalink"}
        </span>
        <div style={toReactStyle("width:30px;height:30px;border-radius:50%;background:#EEF0EE;border:1px solid #D2D5CD;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:#5B6058")}>
          {"김"}
        </div>
      </div>
    </div>
    </>
  );
}
