import { Fragment } from 'react';
import { toReactStyle } from './style';

export function Header({ values }) {
  return (
    <>
    <div className="watchback-header" style={toReactStyle("position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;height:64px;padding:0 32px;background:#FFFFFF;border-bottom:1px solid #E4E6E1;")}>
      <div className="watchback-header-main" style={toReactStyle("display:flex;align-items:center;gap:26px")}>
        <button type="button" aria-label="Watchback 대시보드" style={toReactStyle("display:flex;align-items:center;gap:10px;cursor:pointer;background:none;border:none;padding:0;font-family:inherit;color:inherit")} onClick={values.goToDashboard}>
          <div style={toReactStyle("width:26px;height:26px;border-radius:7px;background:#2F8F5B;display:flex;align-items:center;justify-content:center")}>
            <div style={toReactStyle("width:9px;height:9px;border-radius:2px;background:#FFFFFF;transform:rotate(45deg)")}></div>
          </div>
          <span style={toReactStyle("font-size:16px;font-weight:700;letter-spacing:-0.01em")}>
            {"Watchback"}
          </span>
        </button>
        <div className="watchback-nav" style={toReactStyle("display:flex;align-items:center;gap:4px")}>
          {values.navTabs.map((tab, _index0) => (
            <Fragment key={_index0}>
              <button type="button" style={toReactStyle(`${tab.style};border:none;font-family:inherit`)} onClick={tab.onClick}>
                {`${tab.label}`}
              </button>
            </Fragment>
          ))}
        </div>
      </div>
      <div style={toReactStyle("display:flex;align-items:center;gap:16px")}>
        {values.isPreview && (
          <span style={toReactStyle("font-size:11px;font-weight:600;color:#8B9086;background:#EEF0EE;border-radius:20px;padding:3px 9px;white-space:nowrap")}>
            {"UI Preview"}
          </span>
        )}
        {!values.isPreview && values.dataSource === 'demo' && (
          <span style={toReactStyle("font-size:11px;font-weight:600;color:#9A5A16;background:#FCEFE1;border-radius:20px;padding:3px 9px;white-space:nowrap")}>
            {"Demo 데이터"}
          </span>
        )}
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
